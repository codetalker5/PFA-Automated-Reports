import clickhouse_connect
import streamlit as st
import pandas as pd
from queries import *
import altair as alt
import os
from google import genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch


# -------------------------
# DB CLIENT
# -------------------------
@st.cache_resource
def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=st.secrets['CLICKHOUSE_HOST'],
        port=st.secrets['CLICKHOUSE_PORT'],
        username=st.secrets['CLICKHOUSE_USER'],
        password=st.secrets['CLICKHOUSE_PASSWORD'],
        database=st.secrets['CLICKHOUSE_SCHEMA']
    )

clickhouse_client = get_clickhouse_client()


# -------------------------
# DATA FUNCTION
# -------------------------
def t1(client=clickhouse_client):
    df1 = client.query_df(q1a)
    df1["Indicator"] = 'Students that demonstrate any learning gain'

    df2 = client.query_df(q1b)
    df2["Indicator"] = 'Students with one or more bucket jump'

    df3 = client.query_df(q1c)
    df3["Indicator"] = 'Increase in Students that attained Class appropriate levels'

    df4 = client.query_df(q1d)
    df4["Indicator"] = 'No. of Students'

    # Combine in desired order
    order = [
        "No. of Students",
        "Increase in Students that attained Class appropriate levels",
        "Students that demonstrate any learning gain",
        "Students with one or more bucket jump"
    ]
    df = pd.concat([df4, df3, df1, df2], ignore_index=True)

    pivot_df = df.pivot(index="Indicator", columns="bl_subject", values="pct")
    pivot_df['Average'] = pivot_df.mean(axis=1).round(0).astype(int)

    # Enforce row order
    pivot_df = pivot_df.reindex(order)
    pivot_df = pivot_df.astype(int).reset_index()

    # Keep numeric copy for charts
    numeric_df = pivot_df.copy()

    # Display copy with %
    display_df = pivot_df.copy()
    for i, row in display_df.iterrows():
        if row['Indicator'] != "No. of Students":
            for col in display_df.columns[1:]:
                display_df.at[i, col] = f"{row[col]}%"

    return numeric_df, display_df


# -------------------------
# STREAMLIT PAGE SETUP
# -------------------------
st.set_page_config(layout="wide")
st.title("Student Performance Report")


st.markdown("## 1. About Utkarsh - Remediation Programme for Class 9 students based on Transform Schools' Learning model")
st.markdown("""
    Utkarsh is a 225 hours of programme, spanning 69 days to improve learning outcomes of students in Class 9. Programme aids in
    bridging the learning gaps in Odia, English, Maths and Science. The programme was implemented in 27 districts. The students were
    assessed on elementary level competencies (classes 3-8) at the start of the programme and then supported through collaborative,
    interactive and experiential competency based teaching practices and resources. At the end of the programme, they were tested to
    evaluate the changes in their scores and levels. This report analyses the performance for students, districts and subjects.
""")

numeric_df, display_df = t1()

st.dataframe(display_df)  # table with % formatting


# -------------------------
# CHART DATA PREP
# -------------------------

# Chart uses numeric df without "No. of Students"
chart_df = numeric_df[numeric_df['Indicator'] != "No. of Students"]

# Melt to long format for Altair
df_long = chart_df.melt(id_vars='Indicator', var_name='Subject', value_name='Value')

# Altair chart
# Bar chart
bars = alt.Chart(df_long).mark_bar().encode(
    x=alt.X('Subject:N', title='Subject'),
    xOffset='Indicator:N',
    y=alt.Y('Value:Q', title='Value'),
    color=alt.Color('Indicator:N', title='Indicator'),
    tooltip=['Indicator', 'Subject', 'Value']
)

# Text labels
text = alt.Chart(df_long).mark_text(
    dy=-10,  # lift labels above bars
    fontSize=16
).encode(
    x=alt.X('Subject:N'),
    xOffset='Indicator:N',
    y=alt.Y('Value:Q'),
    text=alt.Text('Value:Q'),
    color=alt.value('black')
)

# Combine bar and text
chart = (bars + text).properties(
    width=600,
    height=400,
    title='Performance by Subject (Grouped by Indicator)'
).configure_legend(
    orient='bottom',
    direction='horizontal',
    title=None
)

st.altair_chart(chart, use_container_width=False)



# -------------------------
# GEMINI SUMMARY
# -------------------------
def c1(gen_client, df):
    data_dict = df.to_dict(orient="split")
    instruction = """
        The below data represents the percentage of students that 
        have met the Indicator's requirements. I want you to summarize 
        and make 4 - 5 numbered point short sentences out of this data.
        Do not output any introductory sentence. Directly output the points.
    """
    content = f'{instruction} \n\n Here is the data: \n {data_dict}'

    response = gen_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=content
    )
    return [p for p in response.text.splitlines() if p.strip()]

try: 
    gen_client = genai.Client()
    gen_df = chart_df.replace(r"%", "", regex=True).apply(pd.to_numeric, errors="ignore")
    summary_points = c1(gen_client, gen_df)

    st.markdown("### 📌 Summary Points")
    for point in summary_points:
        st.markdown(f"- {point}")

except Exception as e:
    st.markdown("## We have encountered some error in summary generation.\n Please contact support team.")

# -------------------------
# PDF GENERATION
# -------------------------
def generate_pdf(df, chart, summary_points, filename="report.pdf"):
    # Save chart as PNG
    chart_path = "chart.png"
    chart.save(chart_path)

    # Create PDF
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("📊 Performance by Subject", styles["Title"]))
    story.append(Spacer(1, 12))

    # Chart
    story.append(Image(chart_path, width=6 * inch, height=3.5 * inch))
    story.append(Spacer(1, 12))

    # Summary Points
    story.append(Paragraph("📌 Summary Points", styles["Heading2"]))
    for point in summary_points:
        story.append(Paragraph(f"• {point}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Data Table
    story.append(Paragraph("📈 Data Table", styles["Heading2"]))
    table_data = [df.columns.to_list()] + df.values.tolist()
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)

    doc.build(story)
    return filename


# -------------------------
# DOWNLOAD BUTTON
# -------------------------
try:
    if st.button("📄 Generate PDF Report"):
        pdf_path = generate_pdf(display_df, chart, summary_points)
        with open(pdf_path, "rb") as f:
            st.download_button("⬇️ Download Full Report", f, file_name="streamlit_report.pdf", mime="application/pdf")

except Exception as e:
    print(e)
    st.markdown("## We have encountered some error.\n Please contact support team.")