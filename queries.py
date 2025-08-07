q1a = """
    with gained as (
        select bl_subject, count(distinct bl_student_id) as student_count from analytics.der_offline_baseline_endline_analysis dobea WHERE learning_gain = 'Learning Gained'
        group by bl_subject
        ),
    total as (
            select bl_subject, count(distinct bl_student_id) as student_count from analytics.der_offline_baseline_endline_analysis dobea
            group by bl_subject
    ) select bl_subject, ROUND(g.student_count/t.student_count, 2) * 100 as pct from gained g left join total t on g.bl_subject = t.bl_subject
    """

q1b = """
    with gained as (
        select bl_subject, count(distinct bl_student_id) as student_count from analytics.der_offline_baseline_endline_analysis dobea WHERE level_jump = 'Jumped Up'
        group by bl_subject
        ),
    total as (
            select bl_subject, count(distinct bl_student_id) as student_count from analytics.der_offline_baseline_endline_analysis dobea
            group by bl_subject
    ) select bl_subject, ROUND(g.student_count/t.student_count, 2) * 100 as pct from gained g left join total t on g.bl_subject = t.bl_subject
    """
q1c = """
    WITH bl AS (
        SELECT 
            bl_subject, 
            COUNT(DISTINCT bl_student_id) AS bl_count 
        FROM analytics.der_offline_baseline_endline_analysis dobea 
        WHERE bl_student_level = 5 
        GROUP BY bl_subject
    ),
    el AS (
        SELECT 
            el_subject, 
            COUNT(DISTINCT el_student_id) AS el_count 
        FROM analytics.der_offline_baseline_endline_analysis dobea 
        WHERE el_student_level = 5
        GROUP BY el_subject
    )
    SELECT 
        b.bl_subject,
        ROUND(((COALESCE(e.el_count, 0) - b.bl_count) * 100.0) / NULLIF(b.bl_count, 0), 0) AS pct
    FROM bl b
    LEFT JOIN el e ON b.bl_subject = e.el_subject
"""