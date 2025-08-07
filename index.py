import clickhouse_connect 
from dotenv import dotenv_values
import streamlit as st
import pandas as pd
from queries import *
import altair as alt
import os
from google import genai


ENV = dotenv_values('C:\\Users\\catal\\OneDrive\\Desktop\\PFA\\PFA_Streamlit_reports\\.env')

@st.cache_resource
def get_client():
    client = clickhouse_connect.get_client(
        host= ENV['CLICKHOUSE_HOST'],
        port= ENV['CLICKHOUSE_PORT'],  # Or 443 for HTTPS if applicable
        username= ENV['CLICKHOUSE_USER'],
        password= ENV['CLICKHOUSE_PASSWORD'],
        database = ENV['CLICKHOUSE_SCHEMA']
    )
    return client

client = get_client()


def t1(client = client):
    df1 = client.query_df(q1a)
    # df1 = df1.applymap(lambda x: f"{x}%" if pd.notnull(x) else x)
    df1["Indicator"] = 'Students that demonstrate any learning gain'
    df2 = client.query_df(q1b)
    # df2 = df2.applymap(lambda x: f"{x}%" if pd.notnull(x) else x)
    df2["Indicator"] = 'Students with one or more bucket jump'
    df3 = client.query_df (q1c)
    df3["Indicator"] = 'Increase in Students that attained Class appropriate levels'

    df = pd.concat([df1, df2,df3], ignore_index=True)
    pivot_df = df.pivot(index="Indicator", columns="bl_subject", values="pct")
    pivot_df['Average'] = pivot_df.mean(axis=1).round(0).astype(int)
    pivot_df = pivot_df.astype(int)
    pivot_df = pivot_df.reset_index()
    
    return pivot_df

st.set_page_config(layout="wide")


df = t1()
st.title("ClickHouse Data in Streamlit")
df = df.set_index('Indicator')
print(df)
st.dataframe(df)



df = df.reset_index().rename(columns={'index': 'Indicator'})

# Melt to long format
df_long = df.melt(id_vars='Indicator', var_name='Subject', value_name='Value')
# Create Altair chart
chart = alt.Chart(df_long).mark_bar().encode(
    x=alt.X('Subject:N', title='Subject'),
    y=alt.Y('Value:Q', title='Value', stack='zero'),
    color=alt.Color('Indicator:N', title='Indicator'),
    tooltip=['Indicator', 'Subject', 'Value']
).properties(
    width=600,
    height=400,
    title='Performance by Subject (Stacked by Indicator)'
).configure_legend(
    orient='bottom',
    direction='horizontal',
    title=None
)

st.altair_chart(chart, use_container_width=False)

def c1(client, df ):
    dict = df.to_dict(orient="split")


    instruction = """
        The below data represents the percentage of students that 
        have met the Indicator's requirements. I want you to summarize 
        and make 4 - 5 numbered point short sentences out of this data.
        Do not output any Introductory sentence. Directly output the points
        """
    content = f'{instruction} \n\n Here is the data: \n {dict}'
    print(content)

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=content
    )
    text = response.text
    points = text.splitlines()
    return points

os.environ['GEMINI_API_KEY'] = ENV['GEMINI_API_KEY']

client = genai.Client()

summary_points = c1(client, df)
st.markdown("### 📌 Summary Points")
for point in summary_points:
    st.markdown(f"- {point}")



import pdfkit
import base64
from io import BytesIO

def generate_pdf(df, chart, summary_points):
    # Save chart as image
    chart_bytes = chart.save('chart.png')
    with open("chart.png", "rb") as image_file:
        chart_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    summary_html = "<br>".join([f"<li>{point}</li>" for point in summary_points])

    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                table, th, td {{ border: 1px solid black; border-collapse: collapse; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2>📊 Performance by Subject</h2>
            <img src="data:image/png;base64,{chart_base64}" width="600"/>
            <h3>📌 Summary Points</h3>
            <ol>{summary_html}</ol>
            <h3>📈 Data Table</h3>
            {df.to_html(index=False)}
        </body>
    </html>
    """

    with open("report.html", "w") as f:
        f.write(html)

    pdfkit.from_file("report.html", "report.pdf")
    return "report.pdf"


import pdfkit
import base64
from io import BytesIO


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
import altair as alt
import pandas as pd


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

    # Chart Image
    story.append(Image(chart_path, width=6*inch, height=3.5*inch))
    story.append(Spacer(1, 12))

    # Data Table
    story.append(Paragraph("📈 Data Table", styles["Heading2"]))

        # Summary Points
    story.append(Paragraph("📌 Summary Points", styles["Heading2"]))
    for point in summary_points:
        story.append(Paragraph(f"• {point}", styles["Normal"]))
    story.append(Spacer(1, 12))


    # Convert df to a list of lists
    table_data = [df.columns.to_list()] + df.values.tolist()

    # Table formatting
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

    # Build PDF
    doc.build(story)
    return filename




if st.button("📄 Generate PDF Report"):
    pdf_path = generate_pdf(df, chart, summary_points)
    with open(pdf_path, "rb") as f:
        st.download_button("⬇️ Download Full Report", f, file_name="streamlit_report.pdf", mime="application/pdf")
