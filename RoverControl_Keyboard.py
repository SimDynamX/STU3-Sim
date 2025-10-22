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

st.OnScreenLogMessage("RoverControl_Keyboard started properly.", "RoverControl_Keyboard", st.Severity.Info)

from pynput import keyboard


def clamp(val, minimum, maximum):
    return min(maximum, max(val, minimum))


controlled_entity: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "ControlledEntity")


def on_press(key : keyboard.Key | keyboard.KeyCode):
    try:
        if key == keyboard.Key.up:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Accelerator"], 1.0)
        
        if key == keyboard.Key.down:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Brake"], 1.0)
        
        if key == keyboard.Key.left:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], -1.0)
        
        if key == keyboard.Key.right:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], 1.0)
        
        if key == keyboard.Key.shift_r:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], True)
        
        if hasattr(key, 'char'):
            if key.char == 'f' or key.char == 'F':
                controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], True)
            
        #     if key.char == 'p' or key.char == 'P':
        #         beginTimeWarpPayload: st.ParamMap = st.ParamMap()
        #         beginTimeWarpPayload.AddParam(st.VarType.entityRef, "Rover", controlled_entity)
        #         st.SimGlobals.DispatchEvent("BeginTimeWarp", beginTimeWarpPayload)
        
    except AttributeError:
        st.logger_info('special key {0} pressed'.format(key))


def on_release(key):
    try:
        if key == keyboard.Key.up:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Accelerator"], 0.0)
        
        if key == keyboard.Key.down:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "Brake"], 0.0)
        
        if key == keyboard.Key.left:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], 0.0)
        
        if key == keyboard.Key.right:
            controlled_entity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], 0.0)
        
        if key == keyboard.Key.shift_r:
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], False)
        
        if key.char == 'f' or key.char == 'F':
            controlled_entity.SetParam(st.VarType.bool, ["ControlCmd", "Flip"], False)
        
    except AttributeError:
        st.logger_info('special key {0} pressed'.format(key))
    
    # if key == keyboard.Key.esc:
    #     # Stop listener
    #     st.logger_info("Program ended")
    #     return False


with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
    listener.join()

st.leave_sim()
