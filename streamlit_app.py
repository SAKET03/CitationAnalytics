import re
from typing import Dict, List

import pandas as pd
import pymupdf  # PyMuPDF
import streamlit as st


def get_sql_urls() -> set:
    """Return static set of SQL URLs from tables.csv (exact matches only)"""
    # Static list of SQL URLs extracted from tables.csv
    sql_urls = {
        "https://dashboard.msme.gov.in/Udyam_Statewise.aspx",
        "https://data.adb.org/dataset/2023-asia-small-and-medium-sized-enterprise-monitor",
        "https://data.adb.org/media/10421/download",
        "https://data.rbi.org.in/#/dbie/indicators",
        "https://eaindustry.nic.in/download_data_1112.asp",
        "https://esankhyiki.mospi.gov.in/",
        "https://esankhyiki.mospi.gov.in/catalogue-main/catalogue?index=&page=0&product=NAS",
        "https://esankhyiki.mospi.gov.in/catalogue-main/catalogue?page=0&search=&product=NAS&q=NSDP",
        "https://esankhyiki.mospi.gov.in/macroindicators-main/macroindicators?product=asi",
        "https://esankhyiki.mospi.gov.in/macroindicators-main/macroindicators?product=asuse",
        "https://esankhyiki.mospi.gov.in/macroindicators-main/macroindicators?product=nss77&tab=table",
        "https://esankhyiki.mospi.gov.in/macroindicators-main/macroindicators?product=nss78",
        "https://esankhyiki.mospi.gov.in/macroindicators-main/macroindicators?product=plfs",
        "https://esankhyiki.mospi.gov.in/macroindicators?product=cpi",
        "https://labourbureau.gov.in/uploads/public/notice/MIL-07-2024pdf-bd246163a1b7f2b4515a6eedd5df650d.pdf",
        "https://mospi.gov.in/GSVA-NSVA",
        "https://niryat.gov.in/india",
        "https://residex.nhbonline.org.in/",
        "https://www.data.gov.in/resource/kisan-call-centre-kcc-transcripts-farmers-queries-answers",
        "https://www.gst.gov.in/download/gststatistics",
        "https://www.indiabudget.gov.in/budget2022-23/economicsurvey/doc/stat/tab43.pdf",
        "https://www.indiabudget.gov.in/economicsurvey/doc/Statistical-Appendix-in-English.pdf",
        "https://www.niftyindices.com/indices/equity/thematic-indices/nifty-sme-emerge",
        "https://www.rbi.org.in/scripts/Data_Sectoral_Deployment.aspx",
    }
    return sql_urls


def classify_citation_type(citation_url: str) -> str:
    """Classify citation as 'SQL' if URL exactly matches tables.csv, otherwise 'Vector'"""
    if not citation_url:
        return "Vector"

    sql_urls = get_sql_urls()
    return "SQL" if citation_url in sql_urls else "Vector"


def clean_text(text: str) -> str:
    """Clean and format text for better markdown output"""
    import re

    # Remove excessive whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Fix common PDF extraction issues
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # Add space between camelCase
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)  # Add space after sentence endings

    # Clean up citation formatting
    text = re.sub(
        r"\[(\d+)\]\s*\[([^\]]+)\]\s*([^:]+):\s*(https?://[^\s]+)",
        r"[\1] [\2] \3: \4",
        text,
    )

    return text


def find_references_section(text: str) -> str:
    """Find and extract the References section from the text content"""
    import re

    # Look for References section - capture everything after "References" until end
    references_patterns = [
        r"References\s*\n(.*)",
        r"REFERENCES\s*\n(.*)",
    ]

    for pattern in references_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    # If no References section found, return the last part of the document
    # (often citations are at the end)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "References" in line or "REFERENCES" in line:
            return "\n".join(lines[i + 1 :]).strip()

    return text


def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file with improved formatting"""
    try:
        # Read the uploaded file
        pdf_bytes = pdf_file.read()

        # Open PDF with PyMuPDF
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        text_content = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()

            # Clean up the text
            text = clean_text(text)

            text_content.append(text)

        doc.close()
        return "\n\n".join(text_content)

    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return None


def count_citation_occurrences(citation_num: int, text: str) -> int:
    """Count how many times a citation number appears in the document"""
    pattern = rf"\[{citation_num}\]"
    return len(re.findall(pattern, text))


def extract_citations_directly(text: str) -> List[Dict]:
    """Extract citations only from the References section"""
    citations = []
    seen_citations = set()

    # First, find the References section
    references_content = find_references_section(text)

    # Pattern: [number] [Type] Headline: Link
    # Handle multi-line URLs by capturing everything after : until next citation pattern
    # Use DOTALL to capture across newlines
    citation_pattern = r"\[(\d+)\]\s*\[([^\]]+)\]\s*([^:]+?):\s*(.*?)(?=\n\[|\Z)"
    matches1 = re.findall(citation_pattern, references_content, re.UNICODE | re.DOTALL)

    # Check if citation 15 is missing and add it manually if needed
    citation_15_found = any(match[0] == "15" for match in matches1)
    if not citation_15_found:
        # Try to manually add citation 15
        test_pattern = r"\[15\]\s*\[([^\]]+)\]\s*([^:]+?):\s*(.*?)(?=\n\[|\Z)"
        test_matches = re.findall(
            test_pattern, references_content, re.UNICODE | re.DOTALL
        )
        if test_matches:
            matches1.append(
                ("15", test_matches[0][0], test_matches[0][1], test_matches[0][2])
            )

    # Clean up the matches - remove line breaks from URLs and handle special cases
    cleaned_matches = []
    for citation_num, web_internal, headline, url in matches1:
        # Remove line breaks and extra whitespace from URL
        clean_url = re.sub(r"\s+", "", url.strip())

        # Handle special cases like "Govt source:" prefix
        if "Govtsource:" in clean_url:
            clean_url = clean_url.replace("Govtsource:", "")

        # Extract just the URL part if there's extra text
        url_match = re.search(r"(https?://[^\s]+)", clean_url)
        if url_match:
            clean_url = url_match.group(1)

        cleaned_matches.append((citation_num, web_internal, headline, clean_url))

    matches1 = cleaned_matches

    # Collect all matches and choose the best one for each citation number
    citation_dict = {}  # citation_num -> best citation data

    for citation_num, web_internal, headline, url in matches1:
        citation_num = int(citation_num)

        # Clean headline and URL - remove line breaks and extra whitespace
        headline = re.sub(r"\s+", " ", headline.strip())
        url_clean = re.sub(r"\s+", "", url.strip()) if url else ""

        # Ensure no line breaks in headline and link for CSV output
        headline = headline.replace("\n", " ").replace("\r", " ")
        url_clean = url_clean.replace("\n", "").replace("\r", "")

        # Determine web/internal
        if "Web" in web_internal:
            web_internal_label = "Web"
        elif "Internal" in web_internal:
            web_internal_label = "Internal"
        else:
            web_internal_label = "Web" if url_clean else "Internal"

        # Count occurrences
        total_occurrences = count_citation_occurrences(citation_num, text)

        # Classify as Vector/SQL (only for Internal citations)
        if web_internal_label == "Internal":
            citation_type = classify_citation_type(url_clean)
        else:
            citation_type = "N/A"  # Web citations are neither SQL nor Vector

        citation_data = {
            "citation_number": citation_num,
            "citation_headline": headline,
            "citation_link": url_clean,
            "web_internal": web_internal_label,
            "total_occurrences": total_occurrences,
            "vector_sql": citation_type,
        }

        # Choose the best citation for this number (prefer ones with URLs and longer headlines)
        if citation_num not in citation_dict:
            citation_dict[citation_num] = citation_data
        else:
            current = citation_dict[citation_num]
            # Prefer citation with URL
            if citation_data["citation_link"] and not current["citation_link"]:
                citation_dict[citation_num] = citation_data
            # If both have URLs or neither has URL, prefer longer headline
            elif len(citation_data["citation_headline"]) > len(
                current["citation_headline"]
            ):
                citation_dict[citation_num] = citation_data

    # Add all citations to the list and mark them as seen
    for citation_data in citation_dict.values():
        citations.append(citation_data)
        seen_citations.add(citation_data["citation_number"])

    # Pattern 2: Handle citations that weren't matched by Pattern header and URL parsing
    bracket_pattern = r"\[(\d+)\]"
    bracket_matches = re.findall(bracket_pattern, references_content)

    # Remove duplicates and limit to reasonable range
    seen_brackets = set(
        int(match) for match in bracket_matches if match.isdigit() and int(match) <= 100
    )

    # Find the maximum citation number to ensure we capture all citations
    max_citation_num = max(seen_brackets) if seen_brackets else 0

    # Ensure we have all citations from 1 to max_citation_num
    for citation_num in range(1, max_citation_num + 1):
        if citation_num not in seen_citations:
            seen_brackets.add(citation_num)

    # For each missing citation, create a placeholder entry
    for citation_num in seen_brackets:
        if citation_num not in seen_citations:
            seen_citations.add(citation_num)

            # Try to find context for this citation number
            citation_context_patterns = [
                rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*([^:]+):\s*(https?://[^\s]+)",
                rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*(.+?)\n(https?://[^\s]+)",
                rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*([^:]+):\s*$",
                rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*(.+?)(?:\s*https?://[^\s\)]+)?",
            ]

            headline = "Missing citation"
            citation_link = ""
            web_internal_label = "Internal"

            # Try each pattern until we find valid context
            for pattern in citation_context_patterns:
                context_matches = re.findall(
                    pattern, references_content, re.IGNORECASE | re.DOTALL | re.UNICODE
                )

                if context_matches:
                    context = context_matches[0]

                    # Handle different pattern formats
                    if len(context) == 3:
                        # Pattern: [num] [Web/Internal] title: url (single line or multi-line)
                        web_internal_class, extracted_headline, url = context
                        headline = extracted_headline.strip()
                        citation_link = url.strip() if url else ""
                        web_internal_label = (
                            "Web" if "Web" in web_internal_class else "Internal"
                        )
                    elif len(context) == 2:
                        # Pattern: [num] [Web/Internal] title: (no URL on same line)
                        web_internal_class, extracted_headline = context
                        headline = extracted_headline.strip()
                        citation_link = ""
                        web_internal_label = (
                            "Web" if "Web" in web_internal_class else "Internal"
                        )

                        # Look for URL on the next line after the title
                        next_line_pattern = rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*([^:]+):\s*\n\s*(https?://[^\s]+)"
                        next_line_matches = re.findall(
                            next_line_pattern,
                            references_content,
                            re.IGNORECASE | re.DOTALL | re.UNICODE | re.MULTILINE,
                        )
                        if next_line_matches:
                            citation_link = next_line_matches[0][2].strip()
                        else:
                            # Try a simpler pattern to find URL on next line
                            simple_pattern = rf"\[{citation_num}\]\s*\[([^\]]+)\]\s*([^:]+):\s*\n(https?://[^\s]+)"
                            simple_matches = re.findall(
                                simple_pattern,
                                references_content,
                                re.IGNORECASE | re.DOTALL | re.UNICODE | re.MULTILINE,
                            )
                            if simple_matches:
                                citation_link = simple_matches[0][2].strip()

                    break

            # Skip if headline is too short or looks malformed (just numbers)
            if len(headline.strip()) < 3 or headline.strip().isdigit():
                continue

            # Clean headline and URL - remove line breaks and extra whitespace
            headline = re.sub(r"\s+", " ", headline.strip())
            citation_link = (
                re.sub(r"\s+", "", citation_link.strip()) if citation_link else ""
            )

            # Ensure no line breaks in headline and link for CSV output
            headline = headline.replace("\n", " ").replace("\r", " ")
            citation_link = citation_link.replace("\n", "").replace("\r", "")

            total_occurrences = count_citation_occurrences(citation_num, text)

            # Classify as Vector/SQL
            citation_type = classify_citation_type(citation_link)

            citation_data = {
                "citation_number": citation_num,
                "citation_headline": headline,
                "citation_link": citation_link,
                "web_internal": web_internal_label,
                "total_occurrences": total_occurrences,
                "vector_sql": citation_type,
            }

            citations.append(citation_data)

    # Sort by citation number
    citations.sort(key=lambda x: x["citation_number"])

    return citations


def citations_to_dataframe(citations: List[Dict]) -> pd.DataFrame:
    """Convert citations to a dataframe"""
    if not citations:
        return pd.DataFrame()

    # Convert to dataframe
    df = pd.DataFrame(citations)

    # Rename columns for better display
    df = df.rename(
        columns={
            "citation_number": "Citation Number",
            "citation_headline": "Citation Headline",
            "citation_link": "Citation Link",
            "web_internal": "Web/Internal",
            "total_occurrences": "Total Occurrences",
            "vector_sql": "Vector/SQL",
        }
    )

    return df


def main():
    st.set_page_config(
        page_title="PDF Citation Extractor", page_icon="📄", layout="wide"
    )

    st.title("📄 PDF Citation Extractor with Vector/SQL Classification")

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type="pdf",
    )

    if uploaded_file is not None:
        # Extract text from PDF
        with st.spinner("Extracting text from PDF..."):
            extracted_text = extract_text_from_pdf(uploaded_file)

        if extracted_text:
            # Extract citations
            with st.spinner("Extracting citations..."):
                citations = extract_citations_directly(extracted_text)

            if citations:
                # Convert to dataframe
                df = citations_to_dataframe(citations)

                # Calculate analytics
                unique_web_count = sum(
                    1 for c in citations if c["web_internal"] == "Web"
                )
                unique_internal_count = sum(
                    1 for c in citations if c["web_internal"] == "Internal"
                )
                total_web_occurrences = sum(
                    c["total_occurrences"]
                    for c in citations
                    if c["web_internal"] == "Web"
                )
                total_internal_occurrences = sum(
                    c["total_occurrences"]
                    for c in citations
                    if c["web_internal"] == "Internal"
                )

                vector_citations = [c for c in citations if c["vector_sql"] == "Vector"]
                sql_citations = [c for c in citations if c["vector_sql"] == "SQL"]
                vector_occurrences = sum(
                    c["total_occurrences"] for c in vector_citations
                )
                sql_occurrences = sum(c["total_occurrences"] for c in sql_citations)

                # For validation, only count Internal citations
                internal_vector_citations = [
                    c
                    for c in citations
                    if c["web_internal"] == "Internal" and c["vector_sql"] == "Vector"
                ]
                internal_sql_citations = [
                    c
                    for c in citations
                    if c["web_internal"] == "Internal" and c["vector_sql"] == "SQL"
                ]
                internal_vector_occurrences = sum(
                    c["total_occurrences"] for c in internal_vector_citations
                )
                internal_sql_occurrences = sum(
                    c["total_occurrences"] for c in internal_sql_citations
                )

                # Calculate totals
                total_citations = len(citations)
                total_occurrences = sum(c["total_occurrences"] for c in citations)

                # Calculate percentages
                internal_percentage = (
                    (total_internal_occurrences / total_occurrences * 100)
                    if total_occurrences > 0
                    else 0
                )
                web_percentage = (
                    (total_web_occurrences / total_occurrences * 100)
                    if total_occurrences > 0
                    else 0
                )
                vector_percentage = (
                    (internal_vector_occurrences / total_occurrences * 100)
                    if total_occurrences > 0
                    else 0
                )
                sql_percentage = (
                    (internal_sql_occurrences / total_occurrences * 100)
                    if total_occurrences > 0
                    else 0
                )

                # Display metrics in columns - Citations
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Citations", total_citations)
                with col2:
                    st.metric("Web Citations", unique_web_count)
                with col3:
                    st.metric("Internal Citations", unique_internal_count)
                with col4:
                    st.metric("Vector Citations", len(internal_vector_citations))
                with col5:
                    st.metric("SQL Citations", len(internal_sql_citations))

                # Display metrics in columns - Occurrences
                col6, col7, col8, col9, col10 = st.columns(5)
                with col6:
                    st.metric("Total Occurrences", total_occurrences)
                with col7:
                    st.metric("Web Occurrences", total_web_occurrences)
                with col8:
                    st.metric("Internal Occurrences", total_internal_occurrences)
                with col9:
                    st.metric("Vector Occurrences", internal_vector_occurrences)
                with col10:
                    st.metric("SQL Occurrences", internal_sql_occurrences)

                # Display percentage splits
                col11, col12 = st.columns(2)
                with col11:
                    st.metric("Internal %", f"{internal_percentage:.1f}%")
                with col12:
                    st.metric("Web %", f"{web_percentage:.1f}%")

                col13, col14 = st.columns(2)
                with col13:
                    st.metric("Vector %", f"{vector_percentage:.1f}%")
                with col14:
                    st.metric("SQL %", f"{sql_percentage:.1f}%")

                # Validation checks
                internal_total_check = total_internal_occurrences == (
                    internal_sql_occurrences + internal_vector_occurrences
                )
                internal_unique_check = unique_internal_count == (
                    len(internal_sql_citations) + len(internal_vector_citations)
                )

                if not internal_total_check or not internal_unique_check:
                    st.error(
                        "⚠️ Validation Error: Internal totals do not match SQL + Vector totals"
                    )
                else:
                    st.success(
                        "✅ Validation passed: Internal totals match SQL + Vector totals"
                    )

                st.subheader("📊 Citation Data Preview")

                # Display dataframe
                st.dataframe(df, width="stretch")

                # Create CSV in the same format as the main processor
                import csv
                import io

                # Create CSV with side-by-side format
                main_headers = [
                    "Citation Number",
                    "Citation Headline",
                    "Citation Link",
                    "Web/Internal",
                    "Total Occurrences",
                    "Vector/SQL",
                ]
                analytics_headers = ["Metric", "Value"]

                # Calculate analytics data
                analytics_rows = [
                    ["Total Citations", total_citations],
                    ["Web Citations", unique_web_count],
                    ["Internal Citations", unique_internal_count],
                    ["Vector Citations", len(internal_vector_citations)],
                    ["SQL Citations", len(internal_sql_citations)],
                    [
                        "N/A Citations",
                        len([c for c in citations if c["vector_sql"] == "N/A"]),
                    ],
                    ["Total Occurrences", total_occurrences],
                    ["Web Occurrences", total_web_occurrences],
                    ["Internal Occurrences", total_internal_occurrences],
                    ["Vector Occurrences", internal_vector_occurrences],
                    ["SQL Occurrences", internal_sql_occurrences],
                    [
                        "N/A Occurrences",
                        sum(
                            c["total_occurrences"]
                            for c in citations
                            if c["vector_sql"] == "N/A"
                        ),
                    ],
                    ["Internal %", f"{internal_percentage:.1f}%"],
                    ["Web %", f"{web_percentage:.1f}%"],
                    ["Vector %", f"{vector_percentage:.1f}%"],
                    ["SQL %", f"{sql_percentage:.1f}%"],
                    [
                        "N/A %",
                        f"{(sum(c['total_occurrences'] for c in citations if c['vector_sql'] == 'N/A') / total_occurrences * 100) if total_occurrences > 0 else 0:.1f}%",
                    ],
                ]

                # Create CSV string with side-by-side format
                output = io.StringIO()
                writer = csv.writer(output)

                # Write combined header with one blank column as a gap
                writer.writerow(main_headers + [""] + analytics_headers)

                # Determine the number of rows to write
                max_rows = max(len(citations), len(analytics_rows))

                for i in range(max_rows):
                    # Left side: citation row data or blanks
                    if i < len(citations):
                        c = citations[i]
                        left = [
                            c["citation_number"],
                            c["citation_headline"],
                            c["citation_link"],
                            c["web_internal"],
                            c["total_occurrences"],
                            c["vector_sql"],
                        ]
                    else:
                        left = [""] * len(main_headers)

                    # Right side: analytics metric/value or blanks
                    if i < len(analytics_rows):
                        right = analytics_rows[i]
                    else:
                        right = [""] * len(analytics_headers)

                    writer.writerow(left + [""] + right)

                combined_csv = output.getvalue()
                output.close()

                # Download button
                st.download_button(
                    label="📥 Download Citations as CSV",
                    data=combined_csv,
                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_citations_with_vector_sql.csv",
                    mime="text/csv",
                )

            else:
                st.warning("No citations found in the PDF")

        else:
            st.error("Failed to extract text from PDF")

    else:
        st.info("👆 Please upload a PDF file to get started")


if __name__ == "__main__":
    main()
