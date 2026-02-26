import gymnasium as gym
from gymnasium import spaces
import numpy as np


class GantryEnv(gym.Env):
    """
    Reinforcement Learning environment for Gantry shipping decisions.

    State : [RUL, Vibration_Level, Hours_Until_Shift_End, Part_Cost]
    Actions: 0 = Standard (Veto)  |  1 = Express (Approve)
    """

    def __init__(self):
        super(GantryEnv, self).__init__()
        self.observation_space = spaces.Box(
            low=0, high=1000, shape=(4,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(2)

    def reset(self, seed=None):
        super().reset(seed=seed)
        # Start with a "Dangerous" state: low RUL, high vibration
        self.state = np.array([5.0, 0.08, 4.0, 350.0], dtype=np.float32)
        return self.state, {}

    def step(self, action):
        rul, vib, hours, cost = self.state

        reward = 0
        if action == 1:  # Approve express shipping
            reward -= cost
            if hours > 2:
                reward += 1000
            else:
                reward -= 500
        else:  # Veto (standard shipping)
            if rul > 2:
                reward += 500
            else:
                reward -= 2000

        done = True
        return self.state, reward, done, False, {}
