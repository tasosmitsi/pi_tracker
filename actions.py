import logging
import alarm

log = logging.getLogger(__name__)

def arm_alarm():
    # do other things, like play a sound
    if alarm.current.arm():
        log.info("Alarm state is being changed to armed...")

def disarm_alarm():
    # do other things, like play a sound
    if alarm.current.disarm():
        log.info("Alarm state is being changed to dis-armed...")
