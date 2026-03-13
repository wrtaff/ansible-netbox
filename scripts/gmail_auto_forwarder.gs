/**
 * Google Apps Script: Gmail Auto-Forwarder
 * 
 * Version: 1.0 (2026-03-12)
 * Refactored for ticket #2738:
 * - Focus on forwarding from @services.discover.com (filtered to 'need-forward-connie').
 * - Handles tag removal and addition post-forwarding.
 * - Supports future expansion for different tags/actions.
 */

// Configuration for forwarding emails based on labels.
// Each entry maps a source label to a target email and optional label management.
const FORWARD_CONFIG = {
  'need-forward-connie': {
    targetEmail: 'mtolivesla@gmail.com',
    removeLabel: 'need-forward-connie', // Remove the trigger tag
    addLabel: 'forwarded-by-script'    // Add the confirmation tag
  },
  // To add a new forwarder in the future, follow this template:
  // 'need-forward-example': {
  //   targetEmail: 'recipient@example.com',
  //   removeLabel: 'need-forward-example',
  //   addLabel: 'forwarded-by-script'
  // }
};

/**
 * Main function to process emails based on the configuration.
 * This should be set to run on a time-driven trigger (e.g., every 15 minutes).
 */
function processEmailsByLabels() {
  for (const labelName in FORWARD_CONFIG) {
    const config = FORWARD_CONFIG[labelName];
    processLabel(labelName, config);
  }
}

/**
 * Process a single label according to the configuration.
 */
function processLabel(labelName, config) {
  const label = GmailApp.getUserLabelByName(labelName);
  
  if (!label) {
    Logger.log('Label not found: ' + labelName);
    return;
  }

  // Find threads with this label
  const threads = label.getThreads();
  if (threads.length === 0) {
    Logger.log('No threads found with label: ' + labelName);
    return;
  }

  Logger.log('Processing ' + threads.length + ' threads for label: ' + labelName);

  // Process each thread
  for (let i = 0; i < threads.length; i++) {
    const thread = threads[i];
    const messages = thread.getMessages();
    
    // Forward the latest message in the thread
    const lastMessage = messages[messages.length - 1];

    try {
      // Forward the message
      lastMessage.forward(config.targetEmail);
      Logger.log('Forwarded thread "' + thread.getFirstMessageSubject() + '" to ' + config.targetEmail);

      // Manage labels
      if (config.addLabel) {
        const addLabelObj = getOrCreateLabel(config.addLabel);
        thread.addLabel(addLabelObj);
      }
      
      if (config.removeLabel) {
        const removeLabelObj = GmailApp.getUserLabelByName(config.removeLabel);
        if (removeLabelObj) {
          thread.removeLabel(removeLabelObj);
        }
      }
    } catch (e) {
      Logger.log('Error processing thread: ' + e.toString());
    }
  }
}

/**
 * Helper function to get a label or create it if it doesn't exist.
 */
function getOrCreateLabel(name) {
  let label = GmailApp.getUserLabelByName(name);
  if (!label) {
    label = GmailApp.createLabel(name);
  }
  return label;
}
