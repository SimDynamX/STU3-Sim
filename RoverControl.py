# THIS COMMENT LINE SHOULD BE THE FIRST LINE OF THE FILE
# DON'T CHANGE ANY OF THE BELOW; NECESSARY FOR JOINING SIMULATION
import os, sys, time, datetime, traceback
import spaceteams as st
def custom_exception_handler(exctype, value, tb):
    error_message = "".join(traceback.format_exception(exctype, value, tb))
    st.logger_fatal(error_message)
    exit(1)
sys.excepthook = custom_exception_handler
st.connect_to_sim(sys.argv)
import numpy as np
# DON'T CHANGE ANY OF THE ABOVE; NECESSARY FOR JOINING SIMULATION
################################################################

st.OnScreenLogMessage("RoverControl started properly.", "RoverControl", st.Severity.Info)

import pygame
from pynput import keyboard

# Initialize Pygame
pygame.init()
pygame.joystick.init()

controller1 : pygame.joystick = None

# Function to find joysticks by GUID
def find_joysticks_by_guid():
    global controller1
    # joysticks = []
    for i in range(pygame.joystick.get_count()):
        joystick = pygame.joystick.Joystick(i)
        joystick.init()
        st.logger_info(f"Joystick {i}: {joystick.get_name()}")
        st.logger_info(f"{joystick.get_guid()}")
        st.logger_info(f"Number of Axes: {joystick.get_numaxes()}")
        st.logger_info(f"Number of Buttons: {joystick.get_numbuttons()}")
        st.logger_info(f"Number of Hats: {joystick.get_numhats()}")
        if joystick.get_guid() == "0300938d5e040000ff02000000007200":
            st.logger_info("Found XBox One Controller")
            controller1 = joystick
        #TODO add other controllers here
        elif joystick.get_guid() == "030083184f0400000204000000000000" and st.GetThisSystem().GetParam(st.VarType.bool, "PreferJoystick"):
            st.logger_info("Found HOTAS Warthog Joystick (RHC)")
            controller1 = joystick
        # elif joystick.get_guid() == "030030364f0400008db6000000000000":
        #     st.logger_info("Found T-Flight HOTAS One Joystick (RHC)")
        #     rhc = joystick
        # elif joystick.get_guid() == "03006a866d04000015c2000000000000":
        #     st.logger_info("Found Logitech Extreme 3D Pro")
        #     rhc = joystick
        # elif joystick.get_guid() == "030010896d04000026c6000000000000":
        #     st.logger_info("Found SpaceNavigator (THC)")
        #     thc = joystick


def remap_input(val: float, in_low: float, in_high: float, out_low: float, out_high: float) -> float:
    f = (val - in_low) / (in_high - in_low)
    return out_low + f * (out_high - out_low)


def remap_input_clamped(val: float, in_low: float, in_high: float, out_low: float, out_high: float) -> float:
    return min(max(remap_input(val, in_low, in_high, out_low, out_high), out_low), out_high)


# Run the program
exit_flag = False
has_joysticks_flag = False

# Joystick GUIDs (Replace these with your joystick GUIDs)
find_joysticks_by_guid()
if controller1 is None:
    st.logger_error("Controller not found!")
    exit_flag = True


controlled_entity: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "ControlledEntity")

# from pynput import keyboard

# def on_press(key):
#     controlled_entity: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "ControlledEntity")
#     try:
#         # X-Axis:
#         if str(key)[1] == 'i':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_X"], 1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "X"], 1.0)
#         elif str(key)[1] == 'k':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_X"], -1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "X"], -1.0)
#         # Y-Axis:
#         if str(key)[1] == 'j':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Y"], 1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Y"], 1.0)
#         elif str(key)[1] == 'l':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Y"], -1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Y"], -1.0)
#         # Z-Axis:
#         if str(key)[1] == 'h':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Z"], 1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Z"], 1.0)
#         elif str(key)[1] == 'n':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Z"], -1.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Z"], -1.0)
#     except AttributeError:
#         st.logger_warn('special key {0} pressed'.format(key))

# def on_release(key):
#     controlled_entity: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "ControlledEntity")
#     try:
#         # X-Axis:
#         if str(key)[1] == 'i':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_X"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "X"], 0.0)
#         elif str(key)[1] == 'k':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_X"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "X"], 0.0)
#         # Y-Axis:
#         if str(key)[1] == 'j':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Y"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Y"], 0.0)
#         elif str(key)[1] == 'l':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Y"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Y"], 0.0)
#         # Z-Axis:
#         if str(key)[1] == 'h':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Z"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Z"], 0.0)
#         elif str(key)[1] == 'n':
#             # controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC_Z"], 0.0)
#             controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "THC", "Z"], 0.0)
#     except AttributeError:
#         st.logger_warn('special key {0} released'.format(key))
#     # if key == keyboard.Key.esc:
#     #     # Stop listener
#     #     st.logger_info("Program ended")
#     #     return False

# listener = keyboard.Listener(on_press=on_press, on_release=on_release)
# listener.start()


# def toggle_mode_rhc(controlled_en : st.Entity):
#     current_mode = controlled_en.GetParam(st.VarType.string, ["ControlCmd", "RHC", "Mode"])
#     if current_mode == "Direct":
#         st.OnScreenAlert("Switching RHC mode to Impulse", "RHC_Mode", st.Severity.Info)
#         controlled_en.SetParam(st.VarType.string, ["ControlCmd", "RHC", "Mode"], "Impulse")
#     elif current_mode == "Impulse":
#         st.OnScreenAlert("Switching RHC mode to Direct", "RHC_Mode", st.Severity.Info)
#         controlled_en.SetParam(st.VarType.string, ["ControlCmd", "RHC", "Mode"], "Direct")

# def toggle_mode_thc(controlled_en : st.Entity):
#     current_mode = controlled_en.GetParam(st.VarType.string, ["ControlCmd", "THC", "Mode"])
#     if current_mode == "Direct":
#         st.OnScreenAlert("Switching THC mode to Impulse", "THC_Mode", st.Severity.Info)
#         controlled_en.SetParam(st.VarType.string, ["ControlCmd", "THC", "Mode"], "Impulse")
#     elif current_mode == "Impulse":
#         st.OnScreenAlert("Switching THC mode to Direct", "THC_Mode", st.Severity.Info)
#         controlled_en.SetParam(st.VarType.string, ["ControlCmd", "THC", "Mode"], "Direct")

# thc_valid = spacenavigator.open()

# toggle_guard_thc = False
# toggle_guard_rhc = False

while not exit_flag:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            exit_flag = True

    button_inputs1 = []
    axis_inputs1 = []
    for axis in range(controller1.get_numaxes()):
        axis_value = controller1.get_axis(axis)
        axis_inputs1.append(axis_value)

    for button in range(controller1.get_numbuttons()):
        button_value = controller1.get_button(button)
        button_inputs1.append(button_value)

    # controlled_entity: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "ControlledEntity")

    # Inputs (for the ThrustMaster T-Flight Hotas One) are:
    # 0: [-1, 1] = [roll left, roll right]
    # 1: [-1, 1] = [pitch down, pitch up]
    # 2: [-1, 1] = [throttle 100%, throttle 0%]
    # 3: -
    # 4: -
    # 5: [-1, 1] = [yaw left, yaw right]
    # 6: -
    # 7: -

    # Inputs (for the Thrustmaster HOTAS Warthog) are:
    # 0: [-1, 1] = [roll left, roll right]
    # 1: [-1, 1] = [pitch down, pitch up]

    controlled_entity.SetParamArray(st.VarType.double, ["ControlCmd", "RawAxes"], axis_inputs1)
    controlled_entity.SetParamArray(st.VarType.bool, ["ControlCmd", "RawButtons"], button_inputs1)
    
    #XBox controller
    if controller1.get_guid() == "0300938d5e040000ff02000000007200": 
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Accelerator"], remap_input(axis_inputs1[5], -1.0, 1.0, 0.0, 1.0))
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Brake"], remap_input(axis_inputs1[4], -1.0, 1.0, 0.0, 1.0))
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], remap_input(axis_inputs1[0], -1.0, 1.0, -1.0, 1.0))
        if(button_inputs1[0]):
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], True)
        else:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], False)
        if(button_inputs1[4]):
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], True)
        else:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], False)
            
    # HOTAS Warthog:
    elif controller1.get_guid() == "030083184f0400000204000000000000":
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Accelerator"], remap_input(axis_inputs1[1], 0.0, -1.0, 0.0, 1.0))
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Brake"], remap_input(axis_inputs1[1], 0, 1.0, 0.0, 1.0))
        controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], remap_input(axis_inputs1[0], -1.0, 1.0, -1.0, 1.0))
        if(button_inputs1[0]): #trigger
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], True)
        else:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], False)
        if(button_inputs1[1]): #pickle button
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], True)
        else:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], False)

    time.sleep(1.0 / st.GetThisSystem().GetParam(st.VarType.double, "LoopFreqHz"))

st.leave_sim()
