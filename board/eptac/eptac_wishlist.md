# EPTAC Technical Wishlist & Problem Log

This document tracks the mission, administrative history, and technical goals for the Eagle & Phenix Mill 3 Technical Advisory Committee (EPTAC). It synthesizes identified problems and desired improvements into logical projects.

---

## 1. Committee Foundation & Administration

### Mission Statement
The mission of the EPTAC is to leverage the technical skills and expertise of residents to provide well-researched, data-driven recommendations to the board, improve building efficiency and systems, and foster transparency and resident engagement. The committee acts in an advisory role, focusing on special projects, future planning, documentation, and proactive identification of technical needs to reduce long-term management workload and ensure infrastructure resilience.

### Membership & Structure
*   **Core Members**: Alayne Gamache (President), Will Taff (Secretary), Aimee Sufka (Board/Policy), Jason Gamache (Infrastructure), Todd Sellers (Dashboard/Special Projects).
*   **Expansion Goal**: Secure "Floor Representatives" to enhance community engagement and distribute communication load (e.g., answering homeowner questions with "TSG is correct").
*   **Governance**: Members are "read in" on their duties as an extension of the board, including the **Duty of Care, Loyalty, and Obedience**.

### History & Formation
*   **Aug 11, 2025**: Board discussed leveraging "free labor" for technical initiatives. Aimee volunteered. Concerns raised about board insurance and protecting volunteers' access to sensitive data (firewalls suggested).
*   **Aug 23, 2025**: Motion carried to formally form the committee.
*   **Sep 4, 2025**: Initial meeting held. Focus identified as prioritizing fire alarm and access control integration due to recent failures. Spectrum Bulk Contract analysis pushed to EPTAC.

---

## 2. Building Automation & HVAC
*Focus: Efficiency, monitoring, and remote control.*

### Wishlist Items
*   **EP3 BAS AAON PRISM Desktop Install**: Implement remote monitoring/control for rooftop units to stop "bleeding money." (**High Priority**).
    *   *Update (Mar 9, 2026)*: Salvaged computer op-checked; needs a hard drive (budget approved by Bill).
*   **Submeter/Instrument AAON**: Detailed tracking of HVAC performance (Will/TSG).
    *   *Update (Mar 9, 2026)*: 12 months of utility data analysis shows 70-85% of building usage is un-submetered (likely the AAON units).
*   **Instrument Geothermal**: Add monitoring to the geothermal system to track performance and predict failures.
*   **Get Data Out of Johnson Control Gear**: Extract and visualize data from existing controllers.
    *   *Update (Mar 9, 2026)*: Investigate Georgia Power API for automated usage graphing.
*   **Stairwell Lighting Modernization**: Replace fluorescents with LEDs.
    *   *Advice (Mar 9, 2026)*: Avoid integrated LED fixtures; use changeable LED bulbs to prevent complete fixture replacement when diodes fail.
*   **Attendant Network Diagram**: Map the specific network path for the attendant desk to resolve stability and display drop-out issues.

### Problems
*   **Geothermal Cage**: The cage hasn't been dived/inspected in years (Brannon 2035 issue).
*   **5th Floor Cooling**: Inconsistent cooling; 5th floor remains hot.
*   **Passive Fire Protection/HVAC Boundaries**: COVID-era practice of leaving fire doors open is "trashy," violates code, and disrupts 5th-floor cooling/pressure. Need to enforce closure via letter to homeowners.
*   **System Blindness**: Lack of historical data; we only know systems fail at the point of failure.
*   **Attendant Desk Stability (Mar 10, 2026)**: Cameras periodically drop from the display at the workstation; suspected network or workstation hardware issue.

---

## 3. Security & Access Control
*Focus: Surveillance, entry management, and resident safety.*

### Wishlist Items
*   **Rooftop/Bay Deck Camera**: Add a camera with audio over the Bay Deck.
    *   *Note*: Budget of $50K mentioned; interest in decibel meters and recording homeowner complaints.
*   **Phone-Based Access**: Implement phone-based door access (NFC/Bluetooth via Google/Apple Wallet) (Todd).
    *   *Update (Mar 9, 2026)*: Contact Donnie with Acom for potential call box upgrades (same hardware as Marina Cove).
*   **Expanded NVR Use**: Use Digital Watchdog triggers/alarms for proactive security (Jason).
    *   **Individual Logins**: Implement individual user accounts for the NVR to track access and improve accountability.
    *   **AI Alerts**: Implement line-crossing and motion alerts for proactive attendant notification.
*   **PTZ & Night Color Cameras**: Investigate high-quality PTZ (Pan-Tilt-Zoom) for the Bay Deck and night color cameras for key entry points.
*   **Revive Front Door Camera**: Investigate/upgrade the Doorbird or equivalent front door system.
*   **"Voice of God" Speaker System**: Investigate a loudspeaker/1MC-style system for security announcements in the parking garage (similar to TSYS garage).
*   **Lobby Egress**: Install "Push to Exit" buttons to prevent residents from being locked in the lobby.
*   **Smart Search & System Health Training**: Advanced training for Board/Management on drawing motion zones and monitoring the admin health dashboard.

### RFIs (Requests for Information)
*   **Attendant Historical Access**: Evaluate the risk/benefit of granting Vic (night attendant) access to historical video footage to assist in immediate incident response. 
    *   *Constraint*: Must be coupled with a confidentiality agreement/NDA to ensure no unauthorized sharing with homeowners.
    *   *Update (Mar 9, 2026)*: Vic is currently restricted from playback to prevent "nosy" behavior; Sammy Watts is the trusted attendant for advanced access.
*   **Law Enforcement Footage Policy**: Define standardized protocols for turning over footage to local authorities.

### Problems
*   **FOB System Discovery**: Lack of understanding of the current access control software/hardware (Will tasked).
*   **Lobby Beeping**: Constant beeping in the lobby is detrimental to home values.
*   **Camera Outage (Mar 9, 2026)**: Exterior camera between Mill 1 and the garage is inoperative post-NVR upgrade; likely a wiring/re-routing issue.
*   **Footage Turnover Request**: Need formal policy to prevent unauthorized sharing with homeowners (require Board/TSG consent).

---

## 4. Fire Safety
*Focus: Compliance, egress, and resident education.*

### Wishlist Items
*   **Safety Education**: Inform homeowners on fire boundaries and safety protocols.
*   **System Audit**: Comprehensive look at fire sensors and boundaries.
*   **Project Management**: Aimee assigned as Project Manager for Fire & Access Control integration.

### Problems
*   **Access Blocks during Alarms**: Doors do not automatically unlock during fire alarms (Critical Safety Issue).
*   **Unreliable Detection**: Current detection system has reliability concerns.

---

## 5. Green Space & Exterior
*Focus: Maintenance, aesthetics, and usability.*

### Wishlist Items
*   **Power on Demand**: Solution to force lights/power ON for events vs. the current restricted timer.
    *   *Update (Mar 9, 2026)*: Photocell location identified on boiler/dumpster building. Bass Electric quote (~$2k) was rejected. Plan to use independent electrician for override switch. (See #3047)
*   **Expanded Garage Wi-Fi**: Extend connectivity for Tesla/EV updates.
*   **Staining/Preservation**: Regular maintenance for furniture and pergolas.

### Problems
*   **Electrical Mess**: Broken fixtures, non-functional sockets, and "Epic" light outages.
*   **Internet Intermittency (Mar 9, 2026)**: Todd Sellers (Unit 522) experiencing intermittent Spectrum service since Jan 30th visit; benchmark case for the building.

---

## 6. Documentation & Operations
*Focus: Knowledge retention, ticketing, and communications.*

### Wishlist Items
*   **GitHub for Infrastructure**: Use for issue tracking and version control of camera/system configurations.
*   **Documentation System**: Implement a Wiki, Notion, or Bookstack for procedures.
*   **IT Asset Management**: TSG to take over tracking and management of building IT infrastructure (Will to provide initial setup and data entry).
*   **Ticketing System**: Formalize how technical/maintenance requests are handled.
*   **Brannon 2.0**: Create a "Dashboard" for Brannon and document his knowledge to keep him in the saddle longer.
*   **Mill 3 Website**: Establish a professional TLD (e.g., `.hoa` or `.org`) for community info and training videos.

### Problems
*   **Lost Technology**: Reliance on institutional knowledge (e.g., Bill Greene's retirement) leads to unmanaged systems.
*   **"The Bus Problem"**: Vulnerability if key staff (Brannon/Bill) are suddenly unavailable.
*   **Response Times**: Need for a service level agreement (e.g., 5 business days) for management emails.

---

## 7. Personnel & Recruitment
*Goal: Ensure every floor and expertise area is represented on the board/committee.*

*   **Potential Candidates**:
    *   Floor 2: Joe or other frequent residents.
    *   Unit 204: Martin (Tech/IT background).
    *   Unit 210/211: "Grant Auer" (Policy/Manual focus).
    *   Floor 4: David Smith or Alan.

---

## Assigned Tasks & Projects
*   **Building Access Control Upgrade**: wrtaff@gmail.com (Start project).
*   **Fire & Access Control Integration**: Aimee (PM), Will & Jason (Workers).
*   **AAON/Prism Software Implementation**: Aimee (PM), Will & Jason (Workers).
*   **Link Bay Deck Cam & Grant Project**: wrtaff@gmail.com.
*   **Phone-Based Access Info**: sellemt@gmail.com (Investigating BT/NFC methods).
