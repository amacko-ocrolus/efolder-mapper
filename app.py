"""Streamlit web UI for the Container Mapping Tool."""

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.ingestion import load_ocrolus_types, load_lender_containers
from services.consensus import build_consensus, write_output_csv
from services import ai_ollama

load_dotenv()

AI_SERVICES = [ai_ollama]

st.set_page_config(page_title="Container Mapper", layout="centered")
st.title("Container Mapper")
st.markdown(
    "Upload an Ocrolus form types CSV and a lender container names file "
    "(CSV or JSON) to generate AI-powered document mappings."
)

ocrolus_file = st.file_uploader(
    "Ocrolus Form Types (CSV)", type=["csv"], key="ocrolus"
)
lender_file = st.file_uploader(
    "Lender Container Names (CSV or JSON)", type=["csv", "json"], key="lender"
)

if st.button("Map", disabled=not (ocrolus_file and lender_file)):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Save uploaded files to temp directory so ingestion module can read them
        ocrolus_path = os.path.join(tmp_dir, ocrolus_file.name)
        lender_path = os.path.join(tmp_dir, lender_file.name)

        with open(ocrolus_path, "wb") as f:
            f.write(ocrolus_file.getvalue())
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

        # --- AI Mapping (parallel) ---
        progress = st.status("Querying AI services...", expanded=True)
        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=len(AI_SERVICES)) as executor:
            future_to_svc = {
                executor.submit(
                    svc.get_mappings, ocrolus_types, lender_containers
                ): svc
                for svc in AI_SERVICES
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

        if len(results) < 1:
            progress.update(label="Failed", state="error")
            st.error(
                f"No AI services succeeded. Only {len(results)} succeeded."
            )
            if errors:
                for svc_name, err in errors.items():
                    st.error(f"{svc_name}: {err}")
            st.stop()

        if errors:
            st.warning(
                f"{len(errors)} service(s) failed. "
                f"Proceeding with {len(results)} results."
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
        write_output_csv(output_path, confident, review, service_names)

        with open(output_path, "rb") as f:
            csv_bytes = f.read()

        st.download_button(
            label="Download Results CSV",
            data=csv_bytes,
            file_name="mapping_output.csv",
            mime="text/csv",
        )
