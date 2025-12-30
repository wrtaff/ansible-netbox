# HS200 Home Assistant Planning

This document outlines the Home Assistant integration planning for the HS200 smart switches.

## Devices

*   **hs200-1**
*   **hs200-2**

## Integration

The devices will be integrated into Home Assistant using the official TP-Link Kasa Smart integration.

## Entities

Each device will expose the following entities in Home Assistant:

*   `switch.<device_name>`

## Automations

*   Automations will be created to control the switches based on time of day and other sensor data.
