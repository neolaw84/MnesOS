import sys

def flatten():
    with open('cartridges/lights-out-demo/yare.yaml', 'r') as f:
        yare = f.read()
    
    yare = yare.replace('state_schema:\n  player:\n    hp:', 'state_schema:\n  player_hp:')
    yare = yare.replace('    name:', '  player_name:')
    yare = yare.replace('    credits:', '  player_credits:')
    yare = yare.replace('    skill_level:', '  player_skill_level:')
    yare = yare.replace('  terminal:\n    locked:', '  terminal_locked:')
    yare = yare.replace('    attempts:', '  terminal_attempts:')
    yare = yare.replace('    reward_tier:', '  terminal_reward_tier:')
    yare = yare.replace('    hack_interacted:', '  terminal_hack_interacted:')
    yare = yare.replace('  world:\n    current_room:', '  world_current_room:')
    yare = yare.replace('    alarm_active:', '  world_alarm_active:')
    
    yare = yare.replace('state.terminal.hack_interacted', 'state.terminal_hack_interacted')
    yare = yare.replace('state.terminal.locked', 'state.terminal_locked')
    yare = yare.replace('state.terminal.attempts', 'state.terminal_attempts')
    yare = yare.replace('state.player.credits', 'state.player_credits')
    yare = yare.replace('state.terminal.reward_tier', 'state.terminal_reward_tier')
    yare = yare.replace('state.world.alarm_active', 'state.world_alarm_active')
    yare = yare.replace('state.player.hp', 'state.player_hp')
    yare = yare.replace('state.world.current_room', 'state.world_current_room')
    
    with open('cartridges/lights-out-demo/yare.yaml', 'w') as f:
        f.write(yare)
        
    with open('cartridges/lights-out-demo/prompt_directives.yaml', 'r') as f:
        prompt = f.read()

    prompt = prompt.replace("bot_memory['world']['alarm_active']", "bot_memory['world_alarm_active']")
    prompt = prompt.replace("bot_memory['terminal']['locked']", "bot_memory['terminal_locked']")
    prompt = prompt.replace("bot_memory['terminal']['hack_interacted']", "bot_memory['terminal_hack_interacted']")
    prompt = prompt.replace("bot_memory['world']['current_room']", "bot_memory['world_current_room']")

    with open('cartridges/lights-out-demo/prompt_directives.yaml', 'w') as f:
        f.write(prompt)

if __name__ == '__main__':
    flatten()
