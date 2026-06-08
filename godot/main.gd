extends Control

# Hold a strong reference to prevent the callback from being garbage-collected.
var _godot_command_callback: JavaScriptObject


func _ready() -> void:
	$VBoxContainer/ShowModalButton.pressed.connect(_on_show_modal_pressed)
	$VBoxContainer/GodotReceiveButton.pressed.connect(_on_godot_receive_pressed)

	if Engine.has_singleton("JavaScriptBridge"):
		# Register this node as the target for godot_send() calls from BOSS.
		_godot_command_callback = JavaScriptBridge.create_callback(_on_boss_command)
		var window := JavaScriptBridge.get_interface("window")
		window.godot_command_handler = _godot_command_callback


# Calls os.ui.showModal() in the BOSS JavaScript layer.
func _on_show_modal_pressed() -> void:
	if Engine.has_singleton("JavaScriptBridge"):
		JavaScriptBridge.eval("os.ui.showModal()")


# Calls the global godot_receive() in notification-manager.js with a test ping.
func _on_godot_receive_pressed() -> void:
	if Engine.has_singleton("JavaScriptBridge"):
		JavaScriptBridge.eval("godot_receive({type: 0, command: 'ping'})")


# Receives a GodotCommand sent from BOSS via godot_send(name, data).
#
# args[0] is a JavaScriptObject with shape: { name: String, data: Object<string:string> }
func _on_boss_command(args: Array) -> void:
	if args.is_empty():
		return
	var cmd: JavaScriptObject = args[0]
	print("BOSS command received — name: ", cmd["name"], "  data: ", cmd["data"])
