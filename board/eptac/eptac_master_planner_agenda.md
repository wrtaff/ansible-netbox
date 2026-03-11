# Eagle & Phenix Technical Advisory Committee (EPTAC) - Master Planner Agenda

This document serves as the top-level planning and tracking repository for the EPTAC. It synthesizes information from technical assessments, committee meetings, and operational transcriptions.

## 1. Executive Summary & Mission
The EPTAC is focused on modernizing building operations ("Brannon 2.0"), improving technical infrastructure, and institutionalizing knowledge to reduce reliance on individual staff members. Key goals for 2026 include HVAC automation, security system optimization, and comprehensive documentation.

---

## 2. 2026 High-Priority Initiatives

### A. AAON Prism (HVAC Automation) - **#1 Priority**
*   **Problem:** Rooftop AAON units are inefficient and currently require physical laptop connection for adjustment. Hallway temperatures are inconsistent.
*   **Solution:** Implement "AAON Prism" software for remote monitoring and control.
*   **Status (Mar 9, 2026):** Will has op-checked a salvaged computer server. It needs a hard drive; Bill Johnson has approved the budget.
*   **Utility Context:** Analysis shows 70-85% of building electric usage is un-submetered, likely due to these AAON units. TSG is currently overpaying WC Bradley for this usage.
*   **Next Steps:** Will to procure hard drive and finalize Prism server setup. Coordinate with Jason for network bridge.

### B. Security & Surveillance Optimization
*   **System:** Digital Watchdog (Blackjack NVR).
*   **Critical Issues:**
    *   **Dead Camera:** Corner of parking garage facing Mill 1 entrance is offline. *Update (Mar 9, 2026)*: Likely a wiring/re-routing issue from the NVR upgrade.
    *   **Blind Spots:** Green Space interior, parking garage intersections, and the vegetation area behind the tower.
    *   **Attendant Desk Performance:** Cameras reported to shut off periodically at the attendant workstation.
*   **Proposals:**
    *   **"Voice of God":** Install speakers in the parking garage for remote verbal warnings to trespassers.
    *   **AI Alerts:** Implement line-crossing/motion alerts to notify attendants. Will to compile a feature "wish list."
    *   **Permission Management:** Sammy Watts granted advanced access; Vic Barkus restricted from playback due to boundary issues.

### C. "Brannon 2.0" (Documentation & Process)
*   **Objective:** Offload stress from Bill Johnson and Brannon Alford by documenting all procedures and vendor contacts.
*   **Communication Policy (Mar 9, 2026)**: Bill Johnson insists all project-level communication go through him (Facilities Manager) rather than directly to Brannon to ensure oversight and chain of command.
*   **IT Asset Management**: Transition the tracking and management of building IT assets (NVRs, switches, AAON controllers) to TSG. Will to perform the initial "heavy lifting" (inventory/tagging) before handoff to Bill.
*   **Tools:**
    *   **Central Repository:** Shared "Dropbox" style structure for manuals and policies.
    *   **Configuration Management:** Use **GitHub** to track system configuration changes (Cameras, Access Control) for version control and rollbacks.
    *   **Ticketing System:** Propose a Google Form/Sheet or sync with existing Sync/AppFolio features to track recurring maintenance (filters, pest control, leaks).

---

## 3. Infrastructure Assessment

### Network & Connectivity (Prism Project)
*   **Rooftop:** AAON Unit Sensors, Weather Station, and Cameras (1-3) connected to a Rooftop Switch.
*   **Backbone:** Fiber link from Rooftop Switch to Ground Floor Switch.
*   **Ground Floor:** Connects to Server and Desk Attendant Workstation via Cat5.

### Spectrum Cable/Fiber (Mill 3)
*   **Topology:** Fiber-to-the-Node (FTTN). Optical Node in the **2nd Floor Cabinet**.
*   **Benchmark Case (Mar 9, 2026):** Todd Sellers (Unit 522) is the primary test case for intermittency. Service improved after Jan 30th visit but remains unstable. Will working with Jesse (Spectrum) to resolve.

---

## 4. Facilities & Maintenance

### Green Space (South Deck)
*   **Power Override (Mar 9, 2026):** Photocell identified on boiler/dumpster building. Quote for override switch rejected; seeking independent electrician for conduit run. (See #3047)
*   **Condition:** Area looks "tired." Needs pressure washing, furniture replacement, and pergola staining.

### General Maintenance
*   **Lighting (Mar 9, 2026):** Moving towards LEDs in stairwells. Recommendation: Changeable LED bulbs only (no integrated fixtures).
*   **Parking Garage:**
    *   **Spot 11:** Designated for WCB Admin/Lawyer; currently underutilized/abused.
    *   **Loading Zone:** Proposal for a 30-minute timer clock to prevent overstays.
*   **Gym:** Equipment is ~16 years old. Discussion on repair (upholstery) vs. replacement with "big iron" or newer treadmills.

---

## 5. Security Incidents & Safety
*   **Recent (Mar 7):** Trespasser (black male, black clothing) seen tampering with windows near Mill 1. Vic contacted police; suspect fled towards the river/dumpster area.
*   **Fire Safety (Critical):** Lobby/hallway doors are *not* automatically unlocking during fire alarms. **Immediate fix required.**
*   **Liability Policy:** Aimee Sufka to draft video/data retention policy (proposed 30-90 day deletion) and confidentiality agreements for staff.

---

## 6. Action Items

| Item | Owner | Status |
| :--- | :--- | :--- |
| Coordinate fix for Lobby Fire Alarm release | EPTAC | **URGENT** |
| Bridge rooftop fiber to ground floor switch | Jason/WireWorks | Pending |
| Finalize AAON Prism Server (Procure Hard Drive) | Will | New |
| Resolve Todd Sellers (Unit 522) Internet Intermittency | Will/Spectrum | New |
| Fix dead Mill 1 entrance camera | Brandon/Jason | New |
| Compile CCTV Feature "Wish List" | Will | New |
| Consult independent electrician for Green Space Override | Bill/Will | New |
| Update Stairwell LED Lighting specs | Brannon/Will | New |
| Draft Video/Data Retention Policy | Aimee | Pending |

---

## 7. Contacts & Board

### Committee Members
*   **Alayne Gamache:** Board President (Communicator/Connector)
*   **Will Taff:** Secretary (Technical/Documentation)
*   **Jason Gamache:** Member (Infrastructure/Digital Watchdog)
*   **Aimee Sufka:** Member/Board (Policy/Legal)

### Support & Staff (TSG)
*   **Bill Johnson:** Facilities Manager
*   **Brannon Alford:** Primary Maintenance (Rockstar)
*   **Vic Barkus:** Night Attendant (Security-focused)
*   **Sammy Watts:** Attendant (Operations)

### Candidates
*   **Treasurer:** Babs (Patricia) or Todd Sellers (Backup).
*   **Technical/IT:** John Martin (Unit 204).
*   **Policy:** Grant (Unit 210/211).
