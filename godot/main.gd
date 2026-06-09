extends Control

# An instance of a GodotController -- used for sending/receiving signals to/from BOSS.
var _delegate: JavaScriptObject

# Strong reference to prevent the callback from being garbage-collected.
var _send_callback: JavaScriptObject


func _ready() -> void:
	$VBoxContainer/SendEventButton.pressed.connect(_on_send_event_pressed)

	if Engine.has_singleton("JavaScriptBridge"):
		# NOTE: BOSS loads Godot apps in an iframe. BOSS sets `boss` on the iframe's
		# contentWindow after the page loads, so it is available as `window.boss` here.
		var window := JavaScriptBridge.get_interface("window")
		if window.boss:
			_delegate = window.boss
			# Expose a JS callback so BOSS can call _delegate.send(...) and reach GDScript.
			_send_callback = JavaScriptBridge.create_callback(_on_boss_send)
			_delegate.send = _send_callback
		else:
			print("No BOSS controller configured for Godot event dispatch")


# Called by BOSS via _delegate.send(cmd).
# cmd is a JavaScriptObject with shape: { name: String, data: Object<string:string> }
func _on_boss_send(args: Array) -> void:
	if args.is_empty():
		return
	var cmd: JavaScriptObject = args[0]
	$VBoxContainer/ReceiveLabel.text = str(cmd["name"])
	print("BOSS send — name: ", cmd["name"], "  data: ", cmd["data"])


# Send message to BOSS controller.
func _on_send_event_pressed() -> void:
	if _delegate:
		# GDScript Dictionaries are NOT automatically converted to JS objects by
		# JavaScriptBridge — they arrive as undefined. Build a JavaScriptObject instead.
		var data: JavaScriptObject = JavaScriptBridge.create_object("Object")
		data["age"] = 42
		var ev: JavaScriptObject = JavaScriptBridge.create_object("Object")
		ev["name"] = "one"
		ev["data"] = data
		_delegate.receive(ev)
	else:
		print("BOSS delegate has not been configured")
