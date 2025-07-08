from PSI_02_19_Patched_POA_All import PSICalculator
import streamlit as st
import pandas as pd
import json

# Page setup
st.set_page_config(page_title="PSI Analyzer", layout="wide")
st.title("🧬 Patient Safety Indicator (PSI) Analyzer")

# Initialize session state
if 'results_df' not in st.session_state:
    st.session_state.results_df = None
if 'error_df' not in st.session_state:
    st.session_state.error_df = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

PSI_CODES = [f"PSI_{i:02}" for i in range(2, 20) if i != 16]

def run_psi_analysis(df, calculator):
    results = []
    errors = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_evaluations = len(df) * len(PSI_CODES)
    current_evaluation = 0
    
    for idx, row in df.iterrows():
        enc_id = row.get("EncounterID", f"Row{idx+1}")
        status_text.text(f"Processing encounter {idx+1}/{len(df)}: {enc_id}")
        
        for psi_code in PSI_CODES:
            try:
                status, rationale, _, _ = calculator.evaluate_psi(row, psi_code)
                results.append({
                    "EncounterID": enc_id,
                    "PSI": psi_code,
                    "Status": status,
                    "Rationale": rationale
                })
            except Exception as e:
                errors.append({
                    "EncounterID": enc_id,
                    "PSI": psi_code,
                    "Error": str(e)
                })
            
            current_evaluation += 1
            progress_bar.progress(current_evaluation / total_evaluations)
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results), pd.DataFrame(errors)

def display_dashboard(df):
    if df is None or "Status" not in df.columns:
        return
        
    total = len(df)
    inclusions = (df["Status"] == "Inclusion").sum()
    exclusions = (df["Status"] == "Exclusion").sum()
    errors = (df["Status"] == "Error").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Evaluated", total)
    col2.metric("Inclusions", inclusions)
    col3.metric("Exclusions", exclusions)
    col4.metric("Errors", errors)

def display_results_table(results_df):
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        psi_filter = st.multiselect("Filter by PSI", sorted(results_df["PSI"].unique()), key="psi_filter")
    with col2:
        status_filter = st.multiselect("Filter by Status", ["Inclusion", "Exclusion", "Error"], key="status_filter")

    # Apply filters
    filtered_df = results_df.copy()
    if psi_filter:
        filtered_df = filtered_df[filtered_df["PSI"].isin(psi_filter)]
    if status_filter:
        filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]

    st.write(f"Showing {len(filtered_df)} of {len(results_df)} results")
    st.dataframe(filtered_df, use_container_width=True)
    
    csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Download Filtered Results", data=csv_data, file_name="PSI_Results.csv")

# File upload
uploaded_file = st.file_uploader("📂 Upload Excel or CSV File", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # Load data
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        df.columns = df.columns.str.strip()
        
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        st.info(f"📊 Dimensions: {df.shape[0]} rows × {df.shape[1]} columns")

        # Initialize PSI Calculator
        try:
            calculator = PSICalculator(
                codes_source_path="PSI_Code_Sets.json",
                psi_definitions_path="PSI_02_19_Compiled_Cleaned.json"
            )
        except Exception as e:
            st.error(f"❌ Failed to initialize PSI Calculator: {e}")
            st.stop()

        # Analysis button
        if st.button("🚀 Analyze PSI", type="primary"):
            with st.spinner("🔬 Running PSI analysis..."):
                results_df, error_df = run_psi_analysis(df, calculator)
                
                # Store results in session state
                st.session_state.results_df = results_df
                st.session_state.error_df = error_df
                st.session_state.analysis_complete = True
            
            st.success(f"✅ Analysis completed! Generated {len(results_df)} results.")

        # Display results if analysis is complete
        if st.session_state.analysis_complete and st.session_state.results_df is not None:
            st.subheader("📊 Dashboard")
            display_dashboard(st.session_state.results_df)

            st.subheader("📋 Results")
            
            # Toggle between view modes
            view_mode = st.radio(
                "Select View Mode:",
                ["All Results (Complete Analysis)", "Inclusions Only (Flagged Events)"],
                horizontal=True
            )
            
            if view_mode == "Inclusions Only (Flagged Events)":
                # Filter to show only inclusions
                inclusions_df = st.session_state.results_df[st.session_state.results_df["Status"] == "Inclusion"]
                
                if not inclusions_df.empty:
                    st.info(f"📍 Showing {len(inclusions_df)} flagged safety events from {st.session_state.results_df['EncounterID'].nunique()} encounters")
                    display_results_table(inclusions_df)
                else:
                    st.success("🎉 No PSI inclusions found - All encounters passed safety checks!")
            else:
                # Show all results with filters
                display_results_table(st.session_state.results_df)

            # Display errors if any
            if st.session_state.error_df is not None and not st.session_state.error_df.empty:
                st.subheader("⚠️ Error Log")
                st.error(f"Found {len(st.session_state.error_df)} errors during analysis:")
                st.dataframe(st.session_state.error_df, use_container_width=True)
                
                error_csv = st.session_state.error_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("⬇️ Download Error Log", data=error_csv, file_name="PSI_Errors.csv")

    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")

else:
    st.info("Upload a file to begin PSI analysis")
    
    # Clear session state when no file is uploaded
    if st.session_state.analysis_complete:
        st.session_state.results_df = None
        st.session_state.error_df = None
        st.session_state.analysis_complete = False