#!/usr/bin/env python3
import os
import sys

# Ensure the script can import from current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import update_wwos_page

content = """'''Bluetooth Proxy''' allows [[Home Assistant]] to communicate with [[Bluetooth]] devices over [[Wi-Fi]], extending its range and eliminating the need for a dedicated Bluetooth adapter on the server.

== Benefits ==
* '''Extended Range:''' Communication with devices across a larger area.
* '''Wireless:''' No physical connection to the HASS server required.
* '''Cost-Effective:''' Uses standard [[ESP32]] hardware.

== Setup Guide ==
Based on XDA Developers guide <ref>https://www.xda-developers.com/i-turned-my-esp32-into-a-bluetooth-proxy/ retrieved 2026-01-10</ref>.

=== Prerequisites ===
* [[ESP32]] device
* [[ESPHome]] add-on in Home Assistant
* USB cable for initial flashing

=== Steps ===
# '''Install ESPHome:''' Add the ESPHome add-on in Home Assistant.
# '''Connect:''' Plug ESP32 into the client machine.
# '''Flash:''' Create a "New device" in ESPHome Dashboard, select serial port, and install.
# '''Configure:''' Add the following to the YAML configuration:
<pre>
esp32_ble_tracker:
  scan_parameters:
    active: true
bluetooth_proxy:
  active: true
</pre>
# '''Deploy:''' Update Wi-Fi credentials and install the new configuration.
# '''Integrate:''' In Home Assistant > Devices & Services, add the detected Bluetooth Proxy.

== External Resources ==
* [https://esphome.io/projects/?type=bluetooth ESPHome Bluetooth Projects]
* [https://www.rogerfrost.com/btproxy/ Roger Frost's Guide]
* [https://peyanski.com/how-to-turn-an-esp32-board-into-a-bluetooth-proxy-for-home-assistant-esphome-bluetooth-proxies/ Peyanski's Guide]
* [https://www.tindie.com/products/harnisch/bluetooth-proxy-based-on-esp32-c3-usb-c/ Pre-made Bluetooth Proxy on Tindie]
* [https://www.creatingsmarthome.com/index.php/2023/03/27/guide-bluetooth-proxy-to-home-assistant-using-esphome/ Guide: Roll your own]
* [https://digiblur.com/2024/09/23/home-assistant-poe-bluetooth-proxy-lilygo/ Digiblur: PoE Bluetooth Proxy]
* [http://trac.home.arpa/ticket/2333 trac #2333 "need build Bluetooth proxy for Home Assistant using ESP32 board"]

[[Category: Bluetooth proxies| ]]"""

if __name__ == "__main__":
    try:
        update_wwos_page.update_wwos_page(
            page_name="Bluetooth proxy", 
            full_content=content, 
            summary="Added setup guide from XDA Developers"
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
