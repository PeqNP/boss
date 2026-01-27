# Notifications & Events

Notifications are (currently) temporary backend app/system information that are communicated to the end-user immediately.

Events are opaque messages sent from a backend app/system, which are designed to be consumed by a front-end app, or BOSS system, to perform a state change in the app.

For example, Wordy sends an event, and notification, when one of your friends makes a guess on a puzzle. The notification lets you know a friend has made a move. The event is used to update the UI within the Wordy app.

The (App structure)[/docs/app-structure.md] shows how to register your controller to recieve events.

## Sending Notifictaions & Events

To send a notification, or event, from your backend app do the following

```python
from lib.server import get_friends, send_events

@router.post("/flip-switch")
@require_user()
async def _guess(boss_user: User, request: Request):
    """ Contrived example showing how to send an event and
    notification. """
    # Query for a list of friends to send message to
    user, friends = await get_friends(request)
    friend_ids = [f.userId for f in friends]
    # Create the event you want to send
    event = {
        "user": user.model_dump_json(),
        "flip_switch": True
    }
    # Send event that the front-end app will consume to update its state.
    #
    # NOTE: The request is required to send messages to Swift notification
    # system, as it contains the session cookie for this user.
    send_events(request, "io.bithead.my-app.switch", data=event, user_ids=friend_ids)
    # Send a notification. This is displayed to every user, so long as
    # they are signed in and BOSS is loaded.
    send_notifications(request, user_ids=friend_ids, title="Switch state", body="The switch was flipped")
