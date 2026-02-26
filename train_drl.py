import os
from stable_baselines3 import PPO
from models.gantry_env import GantryEnv

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "gantry_policy_v1")

env = GantryEnv()
model = PPO("MlpPolicy", env, verbose=1)

print("🧠 Training the Gantry Validator Policy...")
model.learn(total_timesteps=5000)

# Save the brain into /models
model.save(MODEL_PATH)
print(f"✅ Policy saved to {MODEL_PATH}")