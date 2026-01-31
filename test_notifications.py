"""
Test script for Discord notification system
Run this to test Discord webhook notifications without starting the full Assaultron system
"""

from notification_manager import NotificationManager
import time

def main():
    print("=== Assaultron Discord Notification System Test ===\n")

    # Initialize notification manager
    notif = NotificationManager(app_name="Assaultron AI")
    print(f"Discord Webhook: {notif.webhook_url[:50]}...")

    # Test 1: Basic notification
    print("\nTest 1: Sending basic notification...")
    notif.send_notification(
        title="Assaultron AI - Test",
        message="Testing the Discord notification system!",
        force=True
    )
    print("[OK] Sent! Check your Discord channel.")
    time.sleep(2)

    # Test 2: High urgency notification
    print("\nTest 2: High urgency notification...")
    notif.notify_high_urgency(
        emotion="protective",
        goal="alert_scan",
        urgency=0.85
    )
    print("[OK] Sent! Check your Discord channel.")
    time.sleep(2)

    # Test 3: Threat detection
    print("\nTest 3: Threat detection notification...")
    notif.notify_threat_detected(
        threat_level="high",
        entity_count=2
    )
    print("[OK] Sent! Check your Discord channel.")
    time.sleep(2)

    # Test 4: Attention request
    print("\nTest 4: AI attention request...")
    notif.notify_attention_request(
        reason="I have something important to tell you",
        dialogue="Hey! I just noticed something unusual in the camera feed you should check out."
    )
    print("[OK] Sent! Check your Discord channel.")
    time.sleep(2)

    # Test 5: Scheduled check-in
    print("\nTest 5: Scheduled check-in...")
    notif.notify_scheduled_checkin(
        message="Just checking in - everything okay?"
    )
    print("[OK] Sent! Check your Discord channel.")

    print("\n=== All tests completed! ===")
    print("You should have received 5 Discord messages in your webhook channel.")

if __name__ == "__main__":
    main()
