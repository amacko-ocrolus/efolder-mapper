"""Streamlit web UI for the Container Mapping Tool."""

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.ingestion import load_ocrolus_types, load_lender_containers, load_attachment_names
from services.consensus import build_consensus, write_output_csv
from services import ai_openai, ai_anthropic, ai_gemini, history

load_dotenv()

AI_SERVICES = [ai_openai, ai_anthropic, ai_gemini]

PRELOADED_DIR = os.path.join(os.path.dirname(__file__), "preloaded")
ATTACHMENT_NAMES_PATH = os.path.join(PRELOADED_DIR, "table-data.csv")

# Load the form type → attachment name lookup once at startup.
_attachment_names = load_attachment_names(ATTACHMENT_NAMES_PATH)

st.set_page_config(page_title="Container Mapper", layout="wide")
st.title("Container Mapper")
st.markdown(
    "Upload an Ocrolus form types CSV and a lender container names file "
    "(CSV or JSON) to generate AI-powered document mappings."
)

# ---------------------------------------------------------------------------
# Sidebar — service status
# ---------------------------------------------------------------------------
def _check_service_status() -> dict[str, tuple[bool, str]]:
    """Return {service_name: (available, note)} for each AI service."""
    status = {}

    oai_key = os.environ.get("OPENAI_API_KEY", "")
    status["OpenAI"] = (bool(oai_key), "API key set" if oai_key else "OPENAI_API_KEY not set")

    ant_key = os.environ.get("ANTHROPIC_API_KEY", "")
    status["Anthropic"] = (bool(ant_key), "API key set" if ant_key else "ANTHROPIC_API_KEY not set")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    status["Gemini"] = (bool(gemini_key), "API key set" if gemini_key else "GEMINI_API_KEY not set")

    return status


with st.sidebar:
    st.header("Service Status")
    svc_status = _check_service_status()
    for svc_name, (ok, note) in svc_status.items():
        icon = ":white_check_mark:" if ok else ":x:"
        st.markdown(f"{icon} **{svc_name}** — {note}")

    available_count = sum(1 for ok, _ in svc_status.values() if ok)
    if available_count < 2:
        st.warning(
            "At least 2 services must be available to run. "
            "Configure missing API keys in your .env file."
        )
    elif available_count < 3:
        st.info("Mapping will proceed with the available services.")

    st.divider()
    st.caption("Refresh the page to re-check service status.")

# ---------------------------------------------------------------------------
# Ocrolus file — preloaded or upload
# ---------------------------------------------------------------------------
preloaded_files = sorted(
    f for f in os.listdir(PRELOADED_DIR)
    if f.endswith((".csv", ".xlsx")) and not f.startswith(".")
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Ocrolus Form Types")
    if preloaded_files:
        ocrolus_source = st.radio(
            "Source",
            ["Use preloaded file", "Upload custom file"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if ocrolus_source == "Use preloaded file":
            selected = st.selectbox("Select preloaded file", preloaded_files)
            ocrolus_file = None
            ocrolus_preloaded_path = os.path.join(PRELOADED_DIR, selected)
        else:
            ocrolus_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], key="ocrolus")
            ocrolus_preloaded_path = None
    else:
        st.caption("No preloaded files found in `preloaded/`. Upload one below.")
        ocrolus_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], key="ocrolus")
        ocrolus_preloaded_path = None

with col2:
    st.subheader("Lender Container Names")
    lender_file = st.file_uploader(
        "Upload CSV or JSON", type=["csv", "json"], key="lender"
    )

# Determine readiness
ocrolus_ready = ocrolus_preloaded_path is not None or ocrolus_file is not None
lender_ready = lender_file is not None

if st.button("Map", disabled=not (ocrolus_ready and lender_ready)):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Resolve Ocrolus path
        if ocrolus_preloaded_path:
            ocrolus_path = ocrolus_preloaded_path
        else:
            ocrolus_path = os.path.join(tmp_dir, ocrolus_file.name)
            with open(ocrolus_path, "wb") as f:
                f.write(ocrolus_file.getvalue())

        # Save lender file
        lender_path = os.path.join(tmp_dir, lender_file.name)
        with open(lender_path, "wb") as f:
            f.write(lender_file.getvalue())

        # --- Ingest ---
        try:
            ocrolus_types = load_ocrolus_types(ocrolus_path)
            lender_containers = load_lender_containers(lender_path)
        except (FileNotFoundError, ValueError) as e:
            st.error(f"File error: {e}")
            st.stop()

        st.info(
            f"Loaded **{len(ocrolus_types)}** Ocrolus form types and "
            f"**{len(lender_containers)}** lender containers."
        )

        # Only run services that appear available
        active_services = [
            svc for svc in AI_SERVICES
            if svc_status.get(svc.SERVICE_NAME, (False,))[0]
        ]
        if len(active_services) < 2:
            st.error(
                "Fewer than 2 services are available. Check the sidebar and "
                "ensure API keys are set in your .env file."
            )
            st.stop()

        # --- AI Mapping (parallel) ---
        progress = st.status(
            f"Querying {len(active_services)} AI service(s)...", expanded=True
        )
        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=len(active_services)) as executor:
            future_to_svc = {
                executor.submit(
                    svc.get_mappings, ocrolus_types, lender_containers
                ): svc
                for svc in active_services
            }
            for future in as_completed(future_to_svc):
                svc = future_to_svc[future]
                name = svc.SERVICE_NAME
                try:
                    results[name] = future.result()
                    progress.write(f"{name}: received {len(results[name])} mappings.")
                except Exception as e:
                    errors[name] = str(e)
                    progress.write(f"{name}: ERROR — {e}")

        if len(results) < 2:
            progress.update(label="Failed", state="error")
            st.error(
                f"Need at least 2 AI services to succeed. "
                f"Only {len(results)} succeeded."
            )
            for svc_name, err in errors.items():
                st.error(f"{svc_name}: {err}")
            st.stop()

        if errors:
            st.warning(
                f"{len(errors)} service(s) failed during mapping. "
                f"Proceeding with {len(results)} results: "
                + ", ".join(results.keys())
            )

        # --- Consensus ---
        progress.update(label="Building consensus...")
        service_names = list(results.keys())
        confident, review = build_consensus(results, ocrolus_types)

        progress.update(label="Complete!", state="complete")

        st.success(
            f"**{len(confident)}** confident mappings, "
            f"**{len(review)}** need manual review."
        )

        # --- Generate output CSV ---
        output_path = os.path.join(tmp_dir, "mapping_output.csv")
        write_output_csv(output_path, confident, review, service_names, errors, _attachment_names)

        with open(output_path, "rb") as f:
            csv_bytes = f.read()

        st.download_button(
            label="Download Results CSV",
            data=csv_bytes,
            file_name="mapping_output.csv",
            mime="text/csv",
        )

        if history.is_configured():
            try:
                history.save_run(
                    lender_file.name,
                    len(confident),
                    len(review),
                    ", ".join(results.keys()),
                    csv_bytes,
                )
            except Exception as e:
                st.warning(f"Run saved locally but could not be archived: {e}")

# ---------------------------------------------------------------------------
# Previous Runs
# ---------------------------------------------------------------------------
if history.is_configured():
    with st.expander("Previous Runs", expanded=True):
        try:
            runs = history.list_runs()
        except Exception as e:
            st.error(f"Could not load run history: {e}")
            runs = []

        if not runs:
            st.caption("No previous runs found.")
        else:
            for run in runs:
                col1, col2, col3 = st.columns([4, 2, 1])
                label = run["created"].strftime("%b %-d, %Y at %-I:%M %p UTC")
                col1.markdown(f"**{run['lender_filename']}**  \n{label}")
                col2.caption(
                    f"{run['confident_count']} confident · {run['review_count']} review"
                )
                try:
                    csv_data = history.get_run_bytes(run["blob_name"])
                    col3.download_button(
                        "Download",
                        data=csv_data,
                        file_name=os.path.basename(run["blob_name"]),
                        mime="text/csv",
                        key=run["blob_name"],
                    )
                except Exception:
                    col3.caption("unavailable")
