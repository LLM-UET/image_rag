"""
Telecom Package Review App - Streamlit UI for reviewing and saving extracted data.

Features:
- Upload JSON extraction results
- Interactive data editor (st.data_editor)
- Save to MongoDB with upsert
- Statistics and visualization
"""
import json
import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))  # src/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root (for config)

from db.mongo import MongoHandler

# Page configuration
st.set_page_config(
    page_title="Telecom Package Review",
    page_icon="📦",
    layout="wide"
)


def load_json_file(uploaded_file) -> dict:
    """Load and parse uploaded JSON file."""
    try:
        content = uploaded_file.read().decode('utf-8')
        return json.loads(content)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON file: {e}")
        return None
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None


def packages_to_dataframe(packages: list) -> pd.DataFrame:
    """Convert package list to pandas DataFrame for editing."""
    rows = []
    
        for pkg in packages:
            row = {
                "name": pkg.get("name", pkg.get("package_name", "")),
                "partner_name": pkg.get("partner_name", ""),
                "service_type": pkg.get("service_type", ""),
            }
        
        # Flatten attributes
        attributes = pkg.get("attributes", {})
        for key, value in attributes.items():
            row[f"attr_{key}"] = value
        
        # Store original for reference
        row["_original"] = json.dumps(pkg, ensure_ascii=False)
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def dataframe_to_packages(df: pd.DataFrame) -> list:
    """Convert edited DataFrame back to package list."""
    packages = []
    
    for _, row in df.iterrows():
            pkg = {
                "name": row.get("name", row.get("package_name", "")),
                "partner_name": row.get("partner_name", ""),
                "service_type": row.get("service_type", ""),
                "attributes": {}
            }
        
        # Extract attributes (columns starting with attr_)
        for col in df.columns:
            if col.startswith("attr_"):
                attr_name = col[5:]  # Remove "attr_" prefix
                value = row[col]
                if pd.notna(value) and value != "":
                    pkg["attributes"][attr_name] = value
        
        packages.append(pkg)
    
    return packages


def save_to_mongodb(packages: list) -> dict:
    """Save packages to MongoDB."""
    try:
        handler = MongoHandler()
        if handler.connect():
            results = handler.upsert_packages(packages)
            handler.close()
            return results
        else:
            return {"error": "Failed to connect to MongoDB"}
    except Exception as e:
        return {"error": str(e)}


def main():
    st.title("📦 Telecom Package Review")
    st.markdown("Review and edit extracted telecom packages before saving to database.")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # MongoDB settings
        st.subheader("MongoDB Settings")
        mongo_uri = st.text_input(
            "MongoDB URI",
            value="mongodb://localhost:27017",
            help="MongoDB connection string"
        )
        mongo_db = st.text_input(
            "Database",
            value="telecom_db"
        )
        mongo_collection = st.text_input(
            "Collection",
            value="packages"
        )
        
        st.divider()
        
        # Statistics (if connected)
        if st.button("📊 Show DB Statistics"):
            try:
                handler = MongoHandler(mongo_uri, mongo_db, mongo_collection)
                if handler.connect():
                    stats = handler.get_statistics()
                    handler.close()
                    
                    st.metric("Total Packages", stats.get("total_packages", 0))
                    
                    if stats.get("by_partner"):
                        st.write("**By Partner:**")
                        for partner, count in stats["by_partner"].items():
                            st.write(f"  - {partner}: {count}")
                else:
                    st.error("Failed to connect to MongoDB")
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Main content
    st.header("📄 Upload Extraction Results")
    
    uploaded_file = st.file_uploader(
        "Upload JSON file from extraction CLI",
        type=["json"],
        help="Upload the JSON output from telecom_cli.py extract command"
    )
    
    if uploaded_file is not None:
        # Load the JSON data
        data = load_json_file(uploaded_file)
        
        if data:
            # Extract packages
            packages = data.get("packages", data) if isinstance(data, dict) else data
            if not isinstance(packages, list):
                packages = [packages]
            
            # Display metadata
            if isinstance(data, dict) and "source_file" in data:
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"📁 Source: {data.get('source_file', 'Unknown')}")
                with col2:
                    st.info(f"📦 Packages: {len(packages)}")
            
            st.divider()
            
            # Convert to DataFrame for editing
            df = packages_to_dataframe(packages)
            
            # Remove internal column from display
            display_cols = [c for c in df.columns if c != "_original"]
            
            st.header("✏️ Edit Packages")
            st.markdown("Edit the data below. Changes will be reflected when you save.")
            
            # Data editor
            edited_df = st.data_editor(
                df[display_cols],
                num_rows="dynamic",  # Allow adding/removing rows
                use_container_width=True,
                hide_index=True,
                column_config={
                        "name": st.column_config.TextColumn(
                            "Package Name",
                            help="Name or code of the package",
                            required=True
                        ),
                    "partner_name": st.column_config.TextColumn(
                        "Partner",
                        help="Service provider name",
                        required=True
                    ),
                    "service_type": st.column_config.SelectboxColumn(
                        "Service Type",
                        options=["Television", "Internet", "Mobile", "Combo", "Camera", "Other"],
                        required=True
                    ),
                    "attr_price": st.column_config.NumberColumn(
                        "Price (VND)",
                        help="Package price in VND",
                        min_value=0,
                        format="%d"
                    ),
                    "attr_billing_cycle": st.column_config.TextColumn(
                        "Billing Cycle",
                        help="e.g., 1 tháng, 3 tháng, 12 tháng"
                    ),
                    "attr_payment_type": st.column_config.SelectboxColumn(
                        "Payment Type",
                        options=["prepaid", "postpaid", "trả trước", "trả sau"]
                    ),
                }
            )
            
            st.divider()
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("💾 Save to MongoDB", type="primary", use_container_width=True):
                    # Convert back to packages
                    edited_packages = dataframe_to_packages(edited_df)
                    
                    with st.spinner("Saving to MongoDB..."):
                        results = save_to_mongodb(edited_packages)
                    
                    if "error" in results:
                        st.error(f"❌ Save failed: {results['error']}")
                    else:
                        st.success(
                            f"✅ Saved successfully!\n"
                            f"Inserted: {results.get('inserted', 0)}, "
                            f"Updated: {results.get('updated', 0)}, "
                            f"Errors: {results.get('errors', 0)}"
                        )
            
            with col2:
                if st.button("📥 Download JSON", use_container_width=True):
                    edited_packages = dataframe_to_packages(edited_df)
                    json_str = json.dumps(
                        {"packages": edited_packages},
                        ensure_ascii=False,
                        indent=2
                    )
                    st.download_button(
                        label="Download",
                        data=json_str,
                        file_name="edited_packages.json",
                        mime="application/json"
                    )
            
            with col3:
                st.empty()
            
            # Preview section
            with st.expander("👁️ Preview JSON Output"):
                edited_packages = dataframe_to_packages(edited_df)
                st.json(edited_packages[:5])  # Show first 5
                if len(edited_packages) > 5:
                    st.caption(f"... and {len(edited_packages) - 5} more packages")
    
    else:
        # Show instructions when no file uploaded
        st.info("""
        👋 **Getting Started:**
        
        1. **Extract packages** using the CLI:
           ```bash
           python telecom_cli.py extract --input your_document.txt --output results.json
           ```
        
        2. **Upload** the resulting JSON file above
        
        3. **Review and edit** the extracted data
        
        4. **Save** to MongoDB when ready
        """)
        
        # Quick demo with sample data
        if st.checkbox("📝 Try with sample data"):
            sample_packages = [
                {
                    "name": "VIP",
                    "partner_name": "TV360",
                    "service_type": "Television",
                    "attributes": {
                        "price": 80000,
                        "billing_cycle": "1 tháng",
                        "payment_type": "prepaid"
                    }
                },
                {
                    "name": "STANDARD",
                    "partner_name": "TV360",
                    "service_type": "Television",
                    "attributes": {
                        "price": 50000,
                        "billing_cycle": "1 tháng",
                        "payment_type": "prepaid"
                    }
                }
            ]
            
            df = packages_to_dataframe(sample_packages)
            display_cols = [c for c in df.columns if c != "_original"]
            
            st.dataframe(df[display_cols], use_container_width=True)


if __name__ == "__main__":
    main()
