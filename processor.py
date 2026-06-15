import traceback
from pathlib import Path
from typing import Optional, Callable
from config import ROOT, USE_GPU, OUTPUT_DIR, TMP_DIR, _find_ffmpeg, _find_ffprobe
from jobs import Job, _jobs_lock
from transcriber import run_whisper, resolve_whisper_model
from summarizer import run_summary
from clip_utils import parse_summary_to_clips, extract_subtitles_for_clip
from video_editor import cut_and_crop_video

def save_results(stem: str, transcript: str, transcript_srt: str, summary: str) -> None:
    (OUTPUT_DIR / f"{stem}_transcript.txt").write_text(transcript, encoding="utf-8")
    if transcript_srt:
        (OUTPUT_DIR / f"{stem}_transcript.srt").write_text(transcript_srt, encoding="utf-8")
    if summary:
        (OUTPUT_DIR / f"{stem}_summary.txt").write_text(summary, encoding="utf-8")

def process_media(
    media_path: Path,
    *,
    whisper_model_id: Optional[str],
    summary_backend: str,
    with_timestamps: bool,
    layout: str = "vertical_reels",
    job: Optional[Job] = None,
) -> dict:
    from config import GEN_API_KEY
    from summarizer import _resolve_genapi_network
    
    if _resolve_genapi_network(summary_backend) and not GEN_API_KEY:
        raise RuntimeError("GenAPI не настроен. Добавьте GEN_API_KEY в файл .env")

    whisper_model = resolve_whisper_model(whisper_model_id)
    transcript, transcript_srt = run_whisper(
        media_path, whisper_model, with_timestamps=with_timestamps, job=job,
    )
    if job:
        job.log("Транскрипция завершена", progress=90)
    summary = run_summary(
        transcript, summary_backend, transcript_srt=transcript_srt, job=job,
    )
    save_results(media_path.stem, transcript, transcript_srt, summary)

    clips_list = []
    clips_info = parse_summary_to_clips(summary)
    if clips_info:
        # Ограничиваем количество клипов до 15 самых интересных (по оценке),
        # чтобы избежать бесконечной нарезки и переполнения диска
        if len(clips_info) > 15:
            if job:
                job.log(f"Найдено {len(clips_info)} моментов. Выбираем 15 лучших по оценке для экономии времени...")
            # Сортируем по score по убыванию
            clips_info = sorted(clips_info, key=lambda x: x.get("score", 0), reverse=True)[:15]
            # Сортируем обратно по хронологии
            clips_info = sorted(clips_info, key=lambda x: x.get("start_sec", 0))

        if job:
            job.log(f"Нарезаем {len(clips_info)} лучших клипов...", progress=90, status="cutting")
        for i, clip in enumerate(clips_info, 1):
            pct = 90 + int((i / len(clips_info)) * 9)
            if job:
                job.log(f"Нарезка клипа {i}/{len(clips_info)}: {clip['title']}", progress=pct, status="cutting")
            clip_srt_path = TMP_DIR / f"{media_path.stem}_clip_{i}.srt"
            clip_subtitles = extract_subtitles_for_clip(transcript_srt, clip["start_sec"], clip["end_sec"])
            clip_srt_path.write_text(clip_subtitles, encoding="utf-8")
            
            output_clip_path = OUTPUT_DIR / f"{media_path.stem}_clip_{i}.mp4"
            try:
                cut_and_crop_video(
                    video_path=media_path,
                    start_sec=clip["start_sec"],
                    end_sec=clip["end_sec"],
                    clip_srt_path=clip_srt_path if with_timestamps else None,
                    output_clip_path=output_clip_path,
                    ffmpeg_bin=_find_ffmpeg(),
                    ffprobe_bin=_find_ffprobe(),
                    layout=layout,
                    use_gpu=USE_GPU
                )
                clips_list.append({
                    "index": i,
                    "title": clip["title"],
                    "start_str": clip["start_str"],
                    "end_str": clip["end_str"],
                    "score": clip["score"],
                    "description": clip["description"],
                    "filename": output_clip_path.name
                })
            except Exception as e:
                if job:
                    job.log(f"Ошибка при нарезке клипа {i}: {e}")
            
    if job:
        job.log("Обработка полностью завершена", progress=100)

    model_label = whisper_model if isinstance(whisper_model, str) else whisper_model.stem.removeprefix("ggml-")

    return {
        "filename": media_path.name,
        "transcript": transcript,
        "transcript_srt": transcript_srt,
        "summary": summary,
        "whisper_model": model_label,
        "summary_backend": summary_backend,
        "clips": clips_list
    }

def _run_job(
    job: Job,
    work: Callable[[], dict],
) -> None:
    try:
        result = work()
        with _jobs_lock:
            job.result = result
            job.status = "done"
            job.progress = 100
            job.message = "Готово"
    except Exception as e:
        print(f"\n[JOB ERROR] Background task {job.id} failed: {e}")
        traceback.print_exc()
        
        try:
            report_file = ROOT / f"job_crash_{job.id}.txt"
            with report_file.open("w", encoding="utf-8") as rf:
                rf.write("============================================================\n")
                rf.write("              BACKGROUND TASK JOB CRASH REPORT              \n")
                rf.write("============================================================\n")
                rf.write(f"Job ID: {job.id}\n")
                rf.write(f"Status: {job.status}\n")
                rf.write(f"Progress: {job.progress}%\n")
                rf.write(f"Current Message: {job.message}\n")
                rf.write(f"Error Message: {e}\n\n")
                rf.write("--- TRACEBACK ---\n")
                rf.write(traceback.format_exc())
                rf.write("\n============================================================\n")
            print(f"[JOB ERROR] Detailed crash report saved to: {report_file.absolute()}")
        except Exception as log_err:
            print(f"[JOB ERROR] Failed to write job crash report: {log_err}")

        with _jobs_lock:
            job.status = "error"
            job.error = str(e)
            job.message = f"Ошибка: {e}"
