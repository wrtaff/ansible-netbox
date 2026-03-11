# Infrastructure Assessment: Eagle & Phenix Mill 3
**Date:** February 3, 2026
**Reference:** Jan 30 Meeting (Jesse Ovdenk - Spectrum / Bill Johnson - TSG)

## System Overview
The building operates on a **Fiber-to-the-Node (FTTN)** model. The critical "Node" (Optical Receiver) is located physically in the **2nd Floor Cabinet**, not in the basement or on the street.

---

## Technical Description (Network Topology)

### Zone 1: External Backbone
*   **Source:** Spectrum Head End (Warren Williams Road).
*   **Transport:** Dedicated 10 Gbps Fiber Optic circuit (2-strand TX/RX).

### Zone 2: Demarcation (2nd Floor Cabinet)
*   **Location:** 2nd Floor Utility Cabinet.
*   **Hardware:** Optical Node ("The Remote").
*   **Process:** Fiber enters here and is converted to RF (Coaxial) signals.
*   **Status:** Signals here are rated "Perfect/Clean".

### Zone 3: Internal Distribution (IDFs)
*   **Flow:** RF signals are distributed from the 2nd Floor Node:
    *   **Down** to 1st Floor.
    *   **Up** to Floors 3, 4, and 5.
*   **Media:** Shielded Coaxial Riser cables.
*   **Hardware:** Directional Taps (Splitters) located in hallway utility closets.
*   **Correction Note:** Taps on Floors 2-5 were previously sub-optimal; tap dB values were recently "shut around" (adjusted) to correct low signal levels.

### Zone 4: Resident Units (x83)
*   **Modem:** DOCSIS 3.1 (Supports 1.2 Gbps Download).
*   **Roadmap:** 2027 "High Split" upgrade will enable **Symmetric 1Gbps/1Gbps** speeds.
*   **Video:** Xumo Stream Boxes (Full IP-based streaming).
*   **Wi-Fi:** Target move to managed Wi-Fi 7 hardware to resolve unit-level "blind spots."

---

## Infrastructure Diagram (Mermaid)

```mermaid
graph TD
    %% Styles
    classDef fiber fill:#f9f,stroke:#333,stroke-width:2px;
    classDef coax fill:#9cf,stroke:#333,stroke-width:2px;
    classDef unit fill:#fff,stroke:#333,stroke-dasharray: 5 5;

    subgraph ISP_Core [Zone 1: Spectrum Head End]
        HeadEnd[Warren Williams Rd Hub]
        CMTS[Central CMTS]
    end

    subgraph Floor2_Node [Zone 2: 2nd Floor Cabinet]
        FiberDrop[10Gbps Fiber Circuit]:::fiber
        Node[Optical Node / Remote]:::fiber
        Note1[Signal Conversion: Light to RF]
    end

    subgraph Distribution [Zone 3: Vertical Distribution]
        
        subgraph Floor1 [Floor 1]
            Tap1[Directional Tap]:::coax
        end
        
        subgraph Floor2 [Floor 2]
            Tap2[Directional Tap]:::coax
        end

        subgraph UpperFloors [Floors 3-5]
            Tap345[Directional Taps]:::coax
        end
        
        RiserDown[Coax Riser DOWN]:::coax
        RiserUp[Coax Riser UP]:::coax
    end

    subgraph Units [Zone 4: 83 Resident Units]
        WallJack((Coax Wall Jack))
        Modem[DOCSIS 3.1 Modem]
        Router[Wi-Fi 7 Router]
        Xumo[Xumo Stream Box]
        UserDevices(Laptops/Phones/IoT)
    end

    %% Connections
    CMTS --> HeadEnd
    HeadEnd -- "2-Strand Fiber" --> FiberDrop
    FiberDrop --> Node
    
    %% Distribution Logic from 2nd Floor Node
    Node -- "RF Out" --> Tap2
    Node -- "RF Out" --> RiserDown
    Node -- "RF Out" --> RiserUp
    
    RiserDown --> Tap1
    RiserUp --> Tap345
    
    %% Unit Connections
    Tap1 --> WallJack
    Tap2 --> WallJack
    Tap345 --> WallJack
    
    WallJack --> Modem
    Modem -- "1.2 Gbps Down" --> Router
    Router -. "Wi-Fi 7" .-> Xumo
    Router -. "Wi-Fi 7" .-> UserDevices

    %% Link Styles
    linkStyle 1,2 stroke:#ff00ff,stroke-width:3px;
    linkStyle 3,4,5,6,7,8 stroke:#00ccff,stroke-width:3px;
```