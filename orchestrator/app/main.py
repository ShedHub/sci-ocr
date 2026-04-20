from pathlib import Path

from pipeline import run_pipeline


def main() -> None:
    job_id = "job-0001"
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "jobs" / "output" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(job_id)
    print("Pipeline completed")


if __name__ == "__main__":
    main()
