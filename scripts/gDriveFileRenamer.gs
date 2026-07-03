/**
 * Filename: gDriveFileRenamer.gs
 * Description: Modular version supporting both Batch processing and Workspace Add-on.
 * Version: v26_security_update
 * Changes:
 * - Removed ServiceAccount.js dependency.
 * - Migrated to Script Properties for SERVICE_ACCOUNT_JSON storage.
 * - Updated getServiceAccountToken to read directly from the property store.
 */

// --- 1. CONFIGURATION ---
const GCP_PROJECT_ID = 'my-apps-scripts-462022';
const MODEL_NAME = 'gemini-2.5-flash';
const MAX_OUTPUT_TOKENS = 2048; 
const DRIVE_FOLDER_URL = 'https://drive.google.com/drive/u/0/folders/1Qa1jqZB5nbK4OWNfMZkpG7HjwXvLMCzV';
const PROMPT_DOC_URL = 'https://docs.google.com/document/d/1d7NLAm9Ux8u7uMmR9DVuyJuvFLG91ta0SDDC3D_DYfE';
const SCRIPT_VERSION = 'v26_security_update'; 

// --- 2. ADD-ON ENTRY POINTS ---

function onDriveItemsSelected(e) {
  try {
    const fileId = e.drive.activeCursorItem.id;
    const promptDocId = getDriveIdFromUrl(PROMPT_DOC_URL);
    const basePrompt = getPromptFromDoc(promptDocId);
    const result = getSuggestedName(fileId, basePrompt);
    return buildRenameCard(fileId, result.currentName, result.suggestedName);
  } catch (err) {
    return buildErrorCard(err.toString());
  }
}

function buildRenameCard(fileId, oldName, newName) {
  const card = CardService.newCardBuilder();
  const header = CardService.newCardHeader().setTitle('File Naming Assistant');
  const section = CardService.newCardSection()
    .addWidget(CardService.newKeyValue().setTopLabel('Current Name').setContent(oldName).setMultiline(true))
    .addWidget(CardService.newKeyValue().setTopLabel('Suggested Name').setContent(newName).setMultiline(true));
  const action = CardService.newAction().setFunctionName('applyRename').setParameters({fileId: fileId, newName: newName});
  section.addWidget(CardService.newButtonSet().addButton(CardService.newTextButton().setText('Apply Rename').setOnClickAction(action)));
  card.addSection(section);
  return card.build();
}

function buildErrorCard(message) {
  return CardService.newCardBuilder()
    .addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(`Error: ${message}`)))
    .build();
}

function applyRename(e) {
  const fileId = e.parameters.fileId;
  const newName = e.parameters.newName;
  Drive.Files.patch({ title: newName }, fileId);
  return CardService.newActionResponseBuilder().setNotification(CardService.newNotification().setText(`Renamed to: ${newName}`)).build();
}

// --- 3. BATCH PROCESSING ENTRY POINT ---

function runFileRenamer() {
  Logger.log('--- Starting Batch File Renamer ---');
  const folderId = getDriveIdFromUrl(DRIVE_FOLDER_URL);
  const promptDocId = getDriveIdFromUrl(PROMPT_DOC_URL);
  const basePrompt = getPromptFromDoc(promptDocId);

  let files = [];
  let pageToken = null;
  do {
    const fileList = Drive.Files.list({
      q: `'${folderId}' in parents and trashed = false`,
      maxResults: 50,
      pageToken: pageToken
    });
    if (fileList.items) files = files.concat(fileList.items);
    pageToken = fileList.nextPageToken;
  } while (pageToken);

  for (const file of files) {
    const result = getSuggestedName(file.id, basePrompt);
    if (result.suggestedName && result.suggestedName.toLowerCase() !== result.currentName.toLowerCase()) {
      Drive.Files.patch({ title: result.suggestedName }, file.id);
      Logger.log(`Renamed: ${result.currentName} -> ${result.suggestedName}`);
    }
    Utilities.sleep(2000); 
  }
}

// --- 4. CORE ENGINE (Shared) ---

function getSuggestedName(fileId, basePrompt) {
  const file = Drive.Files.get(fileId);
  const currentName = file.title;
  const mimeType = file.mimeType;
  let fileContent = '';
  let tempId = null;

  try {
    if (mimeType === 'application/pdf') {
      const pdfData = convertPdfToText_v2(fileId);
      fileContent = pdfData.text;
      tempId = pdfData.tempId;
    } else if (mimeType === 'application/vnd.google-apps.document') {
      fileContent = DocumentApp.openById(fileId).getBody().getText();
    } else if (mimeType === 'text/plain') {
      fileContent = DriveApp.getFileById(fileId).getBlob().getDataAsString();
    } else if (mimeType === 'application/json') {
      if (file.downloadUrl) fileContent = UrlFetchApp.fetch(file.downloadUrl, { headers: { 'Authorization': 'Bearer ' + getServiceAccountToken() } }).getContentText();
    }

    if (fileContent && fileContent.trim()) {
      const fullPrompt = `${basePrompt}\n\nCURRENT NAME: ${currentName}\n\nCONTENT: ${fileContent.substring(0, 5000)}\n\nNew Name:`;
      let newName = getNewNameFromGemini(fullPrompt, GCP_PROJECT_ID);
      
      if (!newName) return { currentName: currentName, suggestedName: currentName };

      const extension = getFileExtension(currentName);
      if (extension && !newName.endsWith(extension) && !mimeType.includes('google-apps')) newName = `${newName}.${extension}`;
      if (mimeType === 'application/pdf' && !newName.toLowerCase().endsWith('.pdf')) newName = `${newName}.pdf`;
      
      return { currentName: currentName, suggestedName: newName };
    }
  } catch (e) {
    Logger.log(`Error processing ${currentName}: ${e}`);
  } finally {
    if (tempId) try { Drive.Files.remove(tempId); } catch (e) {}
  }
  return { currentName: currentName, suggestedName: currentName };
}

// --- 5. HELPERS (Security Improved) ---

function getServiceAccountToken() {
  const jsonString = PropertiesService.getScriptProperties().getProperty('SERVICE_ACCOUNT_JSON');
  if (!jsonString) throw new Error('Missing SERVICE_ACCOUNT_JSON in Script Properties');
  const key = JSON.parse(jsonString);
  const encode = (obj) => Utilities.base64Encode(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const signatureInput = encode({ "alg": "RS256", "typ": "JWT" }) + "." + encode({ "iss": key.client_email, "scope": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/drive", "aud": "https://oauth2.googleapis.com/token", "exp": Math.floor(Date.now()/1000) + 3600, "iat": Math.floor(Date.now()/1000) });
  const jwt = signatureInput + "." + Utilities.base64Encode(Utilities.computeRsaSha256Signature(signatureInput, key.private_key)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return JSON.parse(UrlFetchApp.fetch("https://oauth2.googleapis.com/token", { "method": "post", "contentType": "application/json", "payload": JSON.stringify({ "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt }) }).getContentText()).access_token;
}

function convertPdfToText_v2(fileId) {
  let temporaryDocId = null;
  const startTime = Date.now();
  try {
    const fileMetadata = Drive.Files.get(fileId);
    const pdfUrl = fileMetadata.downloadUrl;
    const token = getServiceAccountToken();
    if (!pdfUrl || !token) return { text: null, tempId: null };
    const pdfBlob = UrlFetchApp.fetch(pdfUrl, { headers: { 'Authorization': 'Bearer ' + token } }).getBlob();
    pdfBlob.setContentType('application/pdf');
    let tempDoc;
    let attempts = 0;
    while (attempts < 5) {
      try {
        tempDoc = Drive.Files.insert({ title: `[TEMP_OCR] ${fileId}` }, pdfBlob, { ocr: true });
        break; 
      } catch (e) {
        if (e.message.includes("rate limit")) {
          attempts++;
          Utilities.sleep(Math.pow(2, attempts) * 1000 + (Math.random() * 1000));
        } else throw e;
      }
    }
    if (!tempDoc) return { text: null, tempId: null };
    temporaryDocId = tempDoc.id;
    while (Date.now() - startTime < 60000) {
      const updatedMeta = Drive.Files.get(temporaryDocId);
      const exportUrl = updatedMeta.exportLinks ? updatedMeta.exportLinks['text/plain'] : null;
      if (exportUrl) {
        const response = UrlFetchApp.fetch(exportUrl, { muteHttpExceptions: true });
        if (response.getResponseCode() === 200 && !response.getContentText().startsWith('%PDF')) return { text: response.getContentText(), tempId: temporaryDocId };
      }
      Utilities.sleep(5000);
    }
  } catch (e) { return { text: null, tempId: temporaryDocId }; }
  return { text: null, tempId: temporaryDocId };
}

function getNewNameFromGemini(promptText, projectId) {
  const url = `https://us-central1-aiplatform.googleapis.com/v1/projects/${projectId}/locations/us-central1/publishers/google/models/${MODEL_NAME}:generateContent`;
  const options = { 'method': 'post', 'contentType': 'application/json', 'headers': { 'Authorization': 'Bearer ' + getServiceAccountToken() }, 'payload': JSON.stringify({ "contents": [{ "role": "user", "parts": [{ "text": promptText }] }], "generationConfig": { "maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.2 } }), 'muteHttpExceptions': true };
  try {
    const res = UrlFetchApp.fetch(url, options);
    if (res.getResponseCode() === 200) {
      const json = JSON.parse(res.getContentText());
      return json.candidates[0].content.parts[0].text.replace(/^(New File Name:|File Name:|Name:)\s*/i, '').replace(/[`"']/g, '').replace(/[\/\\:?*"<>|]/g, '-').trim();
    }
  } catch (e) { return null; }
  return null;
}

function getPromptFromDoc(docId) {
  try {
    const exportUrl = Drive.Files.get(docId).exportLinks['text/plain'];
    return UrlFetchApp.fetch(exportUrl).getContentText();
  } catch (e) { return null; }
}

function getDriveIdFromUrl(url) {
  const match = url.match(/(?:folders|file|document|presentation|spreadsheets)\/(?:d\/)?([-\w]{25,})/);
  return match ? match[1] : null;
}

function getFileExtension(fileName) {
  if (fileName.match(/\.(gdoc|gsheet|gslides)$/)) return '';
  const parts = fileName.split('.');
  return parts.length > 1 ? parts.pop() : '';
}
