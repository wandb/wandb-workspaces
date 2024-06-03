import random

import numpy as np
import pandas as pd
import wandb


def generate_metrics(run_id, epochs=50):
    """Simulate training data by generating random metrics with some noise."""
    random.seed(run_id)
    np.random.seed(run_id)

    noise_level = 0.05

    epochs_array = np.arange(1, epochs + 1)
    decay_factor = np.exp(-0.1 * epochs_array)

    data = {
        "epoch": epochs_array,
        "train_loss": (np.random.uniform(0.2, 1.0, epochs) * decay_factor)
        + np.random.normal(0, noise_level, epochs),
        "val_loss": (np.random.uniform(0.2, 1.0, epochs) * decay_factor)
        + np.random.normal(0, noise_level, epochs),
        "train_accuracy": (
            np.random.uniform(0.7, 0.9, epochs) + np.linspace(0, 0.1, epochs)
        )
        + np.random.normal(0, noise_level, epochs),
        "val_accuracy": (
            np.random.uniform(0.6, 0.8, epochs) + np.linspace(0, 0.1, epochs)
        )
        + np.random.normal(0, noise_level, epochs),
        "precision": (0.5 + 0.4 * decay_factor)
        + np.random.normal(0, noise_level, epochs),
        "recall": (0.4 + 0.45 * decay_factor)
        + np.random.normal(0, noise_level, epochs),
        "f1_score": (0.5 + 0.4 * decay_factor)
        + np.random.normal(0, noise_level, epochs),
        "learning_rate": np.linspace(0.01, 0.001, epochs)
        + np.random.normal(0, noise_level * 0.01, epochs),
        "train_time_per_epoch": np.random.uniform(10, 20, epochs)
        + np.random.normal(0, noise_level * 10, epochs),
        "val_time_per_epoch": np.random.uniform(2, 5, epochs)
        + np.random.normal(0, noise_level * 5, epochs),
    }

    return pd.DataFrame(data)


def generate_run_with_metrics(**kwargs):
    """Generate a run with simulated training metrics."""
    with wandb.init(**kwargs) as run:
        df = generate_metrics(id(run.id) % 999_999)
        for i, row in df.iterrows():
            run.log(row.to_dict(), step=i)


def generate_sample_runs_with_metrics(entity: str, project: str):
    """Generate sample runs with simuilated training metrics.

    These runs have the same ids and names so a workspace
    generated with this func should be idempotent.
    """
    run_ids = ["1pitw7pm", "yvkevn0m", "2u1g3j1c", "1mbku38n"]
    names = ["valiant-spaceship-1", "vocal-dew-2", "brisk-vortex-3", "smooth-star-4"]

    for run_id, name in zip(run_ids, names):
        generate_run_with_metrics(
            entity=entity,
            project=project,
            id=run_id,
            name=name,
        )
