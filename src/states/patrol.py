import random
import time

# Local import
from src.states.base_state import State

class PatrolState(State):
    def __init__(self, name, bot):
        super().__init__(name, bot)
        self.bot = bot
        self.is_patrol_to_left = True # Patrol direction flag
        self.patrol_turn_point_cnt = 0 # Patrol tuning back counter
        self.idle_move_anchor_x = None
        self.idle_move_direction = "none"
        self.idle_move_until = 0.0
        self.next_idle_move_time = 0.0

    def on_enter(self):
        self.idle_move_anchor_x = None
        self.idle_move_direction = "none"
        self.idle_move_until = 0.0
        self.next_idle_move_time = 0.0

    def on_exit(self):
        pass

    def check_transitions(self):
        return None

    def on_frame(self):
        # Always clear commands from the previous frame/state first.
        self.bot.cmd_move_x = "none"
        self.bot.cmd_move_y = "none"
        self.bot.cmd_action = "none"

        now = time.time()
        x, y = self.bot.loc_player
        h, w = self.bot.img_frame.shape[:2]
        loc_player_ratio = float(x)/float(w)
        left_ratio, right_ratio = self.bot.cfg["patrol"]["range"]
        move_enable = self.bot.cfg["patrol"].get("move_enable", True)

        if move_enable:
            # Check if we need to change patrol direction
            if self.is_patrol_to_left and loc_player_ratio < left_ratio:
                self.patrol_turn_point_cnt += 1
            elif (not self.is_patrol_to_left) and loc_player_ratio > right_ratio:
                self.patrol_turn_point_cnt += 1

            if self.patrol_turn_point_cnt > self.bot.cfg["patrol"]["turn_point_thres"]:
                self.is_patrol_to_left = not self.is_patrol_to_left
                self.patrol_turn_point_cnt = 0

            # Update cmd_move_x
            if self.is_patrol_to_left:
                self.bot.cmd_move_x = "left"
            else:
                self.bot.cmd_move_x = "right"

        # Detect configured monsters in either moving or stationary patrol.
        self.bot.update_cmd_by_mob_detection()
        if not move_enable:
            attack_direction = self.bot.cmd_move_x
            self.bot.cmd_move_x = "none"
            self.bot.cmd_move_y = "none"
            if self.bot.cmd_action == "attack" and \
                    attack_direction in ("left", "right"):
                # Preserve the detected side only for this attack command.
                # The keyboard controller turns briefly, releases the direction
                # key, and then attacks, so stationary patrol does not walk.
                self.bot.cmd_move_x = attack_direction

            # Make an occasional tiny movement while otherwise guarding the
            # same spot. The initial player position is used as an anchor so
            # repeated random choices cannot slowly walk off the platform.
            idle_move_enable = self.bot.cfg["patrol"].get(
                "idle_move_enable", False)
            if idle_move_enable:
                interval_min, interval_max = self.bot.cfg["patrol"].get(
                    "idle_move_interval", [6.0, 14.0])
                duration_min, duration_max = self.bot.cfg["patrol"].get(
                    "idle_move_duration", [0.16, 0.28])
                max_offset = self.bot.cfg["patrol"].get(
                    "idle_move_max_offset", 35)

                if self.idle_move_anchor_x is None:
                    self.idle_move_anchor_x = x
                    self.next_idle_move_time = now + random.uniform(
                        min(interval_min, interval_max),
                        max(interval_min, interval_max))

                if now < self.idle_move_until:
                    if self.bot.cmd_action == "none":
                        self.bot.cmd_move_x = self.idle_move_direction
                elif now >= self.next_idle_move_time and \
                        self.bot.cmd_action == "none":
                    if x <= self.idle_move_anchor_x - max_offset:
                        self.idle_move_direction = "right"
                    elif x >= self.idle_move_anchor_x + max_offset:
                        self.idle_move_direction = "left"
                    else:
                        self.idle_move_direction = random.choice(
                            ["left", "right"])

                    duration = random.uniform(
                        min(duration_min, duration_max),
                        max(duration_min, duration_max))
                    self.idle_move_until = now + duration
                    self.next_idle_move_time = self.idle_move_until + \
                        random.uniform(
                            min(interval_min, interval_max),
                            max(interval_min, interval_max))
                    self.bot.cmd_move_x = self.idle_move_direction

        # Legacy patrol mode attacks periodically without looking for a target.
        # Once monster detection is enabled, only update_cmd_by_mob_detection()
        # is allowed to request an attack.
        detect_monsters = self.bot.cfg["patrol"].get("detect_monsters", False)
        if not detect_monsters and time.time() - self.bot.t_last_attack > \
            self.bot.cfg["patrol"]["patrol_attack_interval"]:
            self.bot.cmd_action = "attack"
            self.bot.t_last_attack = time.time()

        # Random recovery is unsafe in stationary mode because it can make the
        # character walk or jump off a small platform.
        if move_enable and self.bot.is_player_stuck():
            self.bot.update_cmd_by_random()

        # send command to keyboard controller
        self.bot.kb.set_command(self.bot.cmd_move_x + ' ' + \
                                self.bot.cmd_move_y + ' ' + \
                                self.bot.cmd_action)
