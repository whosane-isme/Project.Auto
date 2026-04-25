"""
Test script for adam_action handler with real WhatsApp credentials.

Instructions:
1. Get credentials from Muammal:
   - ADAM_SERVICE_KEY: The authorization token for the whatsapp service
   - connection_id: A valid WhatsApp connection ID for testing
   - test_number: A valid WhatsApp-enabled phone number to send to (format: +1234567890)

2. Update the DEBUG CONFIGURATION section below with actual values

3. Run this script:
   python test_adam_action.py

4. Check that:
   - HTTP status is 200 or 202
   - The message appears in the test WhatsApp inbox
"""

import asyncio
import os
from handlers import HANDLERS

# DEBUG CONFIGURATION - Update these with real values from Muammal
DEBUG_SERVICE_KEY = "YOUR_ADAM_SERVICE_KEY_HERE"
DEBUG_CONNECTION_ID = "YOUR_DEV_CONNECTION_ID_HERE"
DEBUG_TEST_NUMBER = "YOUR_TEST_WHATSAPP_NUMBER_HERE"


async def main():
    # Set the environment variable
    os.environ["ADAM_SERVICE_KEY"] = DEBUG_SERVICE_KEY

    if not DEBUG_SERVICE_KEY or DEBUG_SERVICE_KEY == "YOUR_ADAM_SERVICE_KEY_HERE":
        print("❌ ERROR: Please update DEBUG_SERVICE_KEY with real credentials from Muammal")
        return

    if not DEBUG_CONNECTION_ID or DEBUG_CONNECTION_ID == "YOUR_DEV_CONNECTION_ID_HERE":
        print("❌ ERROR: Please update DEBUG_CONNECTION_ID with a dev ID from Muammal")
        return

    if not DEBUG_TEST_NUMBER or DEBUG_TEST_NUMBER == "YOUR_TEST_WHATSAPP_NUMBER_HERE":
        print("❌ ERROR: Please update DEBUG_TEST_NUMBER with a valid test number")
        return

    print("🔄 Testing adam_action handler with whatsapp.send_freeform...")
    print(f"   Connection ID: {DEBUG_CONNECTION_ID}")
    print(f"   To: {DEBUG_TEST_NUMBER}")
    print(f"   Message: automation test from Task 12")

    try:
        out = await HANDLERS["adam_action"](
            {
                "action": "whatsapp.send_freeform",
                "params": {
                    "connection_id": DEBUG_CONNECTION_ID,
                    "to": DEBUG_TEST_NUMBER,
                    "text": "automation test"
                }
            },
            {},
            None
        )

        print(f"\n✅ Request successful!")
        print(f"   Status: {out['status']}")
        print(f"   Body: {out['body']}")

        if out["status"] in (200, 202):
            print("\n✅ Status code is 200 or 202 (expected)")
            print("\n📱 Please check that the message arrived in the test WhatsApp inbox")
        else:
            print(f"\n⚠️  Unexpected status code: {out['status']}")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   Message: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())

