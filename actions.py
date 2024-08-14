import config

def arm_alarm():
    # do other things, like play a sound
    # save also the alarm state in a file
    if config.alarm_state == 0:
        print("Alarm state is being changed to armed...")
        config.alarm_state = 1

def disarm_alarm():
    # do other things, like play a sound
    # save also the alarm state in a file
    if config.alarm_state == 1:
        print("Alarm state is being changed to dis-armed...")
        config.alarm_state = 0
