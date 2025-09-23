-- 人員覆蓋率統計：全公司覆蓋率（週）
WITH DateBounds AS (
    SELECT
        MIN(CAST(e.InDate AS DATE)) AS min_in_date,
        MAX(CAST(ISNULL(e.OutDate, CAST(GETDATE() AS DATE)) AS DATE)) AS max_out_date
    FROM empbas_app AS e WITH (NOLOCK)
),
ActiveBounds AS (
    SELECT
        MIN(CAST(a.ActivateTime AS DATE)) AS min_active_date,
        MAX(CAST(a.ActivateTime AS DATE)) AS max_active_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
),
Boundaries AS (
    SELECT
        COALESCE(ab.min_active_date, db.min_in_date, CAST(GETDATE() AS DATE)) AS min_date,
        COALESCE(ab.max_active_date, db.max_out_date, CAST(GETDATE() AS DATE)) AS max_date
    FROM DateBounds AS db
    CROSS JOIN ActiveBounds AS ab
),
WeekCalendar AS (
    SELECT
        0 AS week_index,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.min_date) % 7, b.min_date) AS week_start,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.max_date) % 7, b.max_date) AS max_week_start
    FROM Boundaries AS b
    UNION ALL
    SELECT
        week_index + 1,
        DATEADD(WEEK, 1, week_start),
        max_week_start
    FROM WeekCalendar
    WHERE DATEADD(WEEK, 1, week_start) <= max_week_start
),
Weeks AS (
    SELECT
        wc.week_start,
        DATEADD(DAY, 6, wc.week_start) AS week_end,
        DATEPART(ISO_WEEK, wc.week_start) AS iso_week,
        DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)) AS iso_year,
        CONCAT(
            DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)),
            '-W',
            RIGHT('00' + CAST(DATEPART(ISO_WEEK, wc.week_start) AS VARCHAR(2)), 2)
        ) AS week_label
    FROM WeekCalendar AS wc
),
FirstActivation AS (
    SELECT
        a.EmpId,
        MIN(CAST(a.ActivateTime AS DATE)) AS first_activate_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
    GROUP BY a.EmpId
),
Employment AS (
    SELECT
        e.EmpId,
        CAST(e.InDate AS DATE) AS in_date,
        CAST(e.OutDate AS DATE) AS out_date,
        fa.first_activate_date
    FROM empbas_app AS e WITH (NOLOCK)
    LEFT JOIN FirstActivation AS fa
        ON fa.EmpId = e.EmpId
),
WeeklyEmployment AS (
    SELECT
        w.week_start,
        COUNT(DISTINCT CASE WHEN em.EmpId IS NOT NULL THEN em.EmpId END) AS total_employees
    FROM Weeks AS w
    LEFT JOIN Employment AS em
        ON em.in_date <= w.week_end
       AND (em.out_date IS NULL OR em.out_date > w.week_start)
    GROUP BY w.week_start
),
WeeklyCoverage AS (
    SELECT
        w.week_start,
        COUNT(DISTINCT em.EmpId) AS covered_employees
    FROM Weeks AS w
    LEFT JOIN Employment AS em
        ON em.in_date <= w.week_end
       AND (em.out_date IS NULL OR em.out_date > w.week_start)
       AND em.first_activate_date IS NOT NULL
       AND em.first_activate_date <= w.week_end
    GROUP BY w.week_start
)
SELECT
    w.iso_year,
    w.iso_week,
    w.week_label,
    w.week_start AS stat_date,
    ISNULL(c.covered_employees, 0) AS covered_employees,
    ISNULL(t.total_employees, 0) AS total_employees,
    CAST(
        100.0 * ISNULL(c.covered_employees, 0)
        / NULLIF(ISNULL(t.total_employees, 0), 0)
        AS DECIMAL(5, 2)
    ) AS coverage_rate_percent
FROM Weeks AS w
LEFT JOIN WeeklyEmployment AS t
    ON t.week_start = w.week_start
LEFT JOIN WeeklyCoverage AS c
    ON c.week_start = w.week_start
ORDER BY w.week_start
OPTION (MAXRECURSION 32767);


-- 人員覆蓋率統計：各部門覆蓋率（週）
WITH DateBounds AS (
    SELECT
        MIN(CAST(e.InDate AS DATE)) AS min_in_date,
        MAX(CAST(ISNULL(e.OutDate, CAST(GETDATE() AS DATE)) AS DATE)) AS max_out_date
    FROM empbas_app AS e WITH (NOLOCK)
),
ActiveBounds AS (
    SELECT
        MIN(CAST(a.ActivateTime AS DATE)) AS min_active_date,
        MAX(CAST(a.ActivateTime AS DATE)) AS max_active_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
),
Boundaries AS (
    SELECT
        COALESCE(ab.min_active_date, db.min_in_date, CAST(GETDATE() AS DATE)) AS min_date,
        COALESCE(ab.max_active_date, db.max_out_date, CAST(GETDATE() AS DATE)) AS max_date
    FROM DateBounds AS db
    CROSS JOIN ActiveBounds AS ab
),
WeekCalendar AS (
    SELECT
        0 AS week_index,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.min_date) % 7, b.min_date) AS week_start,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.max_date) % 7, b.max_date) AS max_week_start
    FROM Boundaries AS b
    UNION ALL
    SELECT
        week_index + 1,
        DATEADD(WEEK, 1, week_start),
        max_week_start
    FROM WeekCalendar
    WHERE DATEADD(WEEK, 1, week_start) <= max_week_start
),
Weeks AS (
    SELECT
        wc.week_start,
        DATEADD(DAY, 6, wc.week_start) AS week_end,
        DATEPART(ISO_WEEK, wc.week_start) AS iso_week,
        DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)) AS iso_year,
        CONCAT(
            DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)),
            '-W',
            RIGHT('00' + CAST(DATEPART(ISO_WEEK, wc.week_start) AS VARCHAR(2)), 2)
        ) AS week_label
    FROM WeekCalendar AS wc
),
RecursiveOrg AS (
    SELECT
        OrgId AS RootOrgId,
        OrgName AS RootOrgName,
        OrgId,
        OrgName,
        SuperOrgId
    FROM ClassOrg WITH (NOLOCK)
    WHERE RIGHT(OrgId, 4) = '0000'
      AND OrgId <> '10000'
    UNION ALL
    SELECT
        r.RootOrgId,
        r.RootOrgName,
        c.OrgId,
        c.OrgName,
        c.SuperOrgId
    FROM ClassOrg AS c WITH (NOLOCK)
    INNER JOIN RecursiveOrg AS r
        ON c.SuperOrgId = r.OrgId
),
EmployeeOrg AS (
    SELECT
        e.EmpId,
        CAST(e.InDate AS DATE) AS in_date,
        CAST(e.OutDate AS DATE) AS out_date,
        COALESCE(r.RootOrgId, c.OrgId, 'UNASSIGNED') AS root_org_id,
        COALESCE(r.RootOrgName, c.OrgName, N'未定義') AS root_org_name
    FROM empbas_app AS e WITH (NOLOCK)
    LEFT JOIN ClassOrg AS c WITH (NOLOCK)
        ON e.UnitId = c.OrgId
    LEFT JOIN RecursiveOrg AS r
        ON c.OrgId = r.OrgId
),
FirstActivation AS (
    SELECT
        a.EmpId,
        MIN(CAST(a.ActivateTime AS DATE)) AS first_activate_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
    GROUP BY a.EmpId
),
DepartmentEmployment AS (
    SELECT
        eo.EmpId,
        eo.root_org_id,
        eo.root_org_name,
        eo.in_date,
        eo.out_date,
        fa.first_activate_date
    FROM EmployeeOrg AS eo
    LEFT JOIN FirstActivation AS fa
        ON fa.EmpId = eo.EmpId
),
OrgList AS (
    SELECT DISTINCT
        de.root_org_id,
        de.root_org_name
    FROM DepartmentEmployment AS de
),
WeekOrg AS (
    SELECT
        w.week_start,
        w.week_end,
        w.iso_week,
        w.iso_year,
        w.week_label,
        o.root_org_id,
        o.root_org_name
    FROM Weeks AS w
    CROSS JOIN OrgList AS o
),
DepartmentTotals AS (
    SELECT
        wo.week_start,
        wo.root_org_id,
        COUNT(DISTINCT CASE WHEN de.EmpId IS NOT NULL THEN de.EmpId END) AS total_employees
    FROM WeekOrg AS wo
    LEFT JOIN DepartmentEmployment AS de
        ON de.root_org_id = wo.root_org_id
       AND de.in_date <= wo.week_end
       AND (de.out_date IS NULL OR de.out_date > wo.week_start)
    GROUP BY wo.week_start, wo.root_org_id
),
DepartmentCoverage AS (
    SELECT
        wo.week_start,
        wo.root_org_id,
        COUNT(DISTINCT de.EmpId) AS covered_employees
    FROM WeekOrg AS wo
    LEFT JOIN DepartmentEmployment AS de
        ON de.root_org_id = wo.root_org_id
       AND de.in_date <= wo.week_end
       AND (de.out_date IS NULL OR de.out_date > wo.week_start)
       AND de.first_activate_date IS NOT NULL
       AND de.first_activate_date <= wo.week_end
    GROUP BY wo.week_start, wo.root_org_id
)
SELECT
    wo.iso_year,
    wo.iso_week,
    wo.week_label,
    wo.week_start AS stat_date,
    NULLIF(wo.root_org_id, 'UNASSIGNED') AS root_org_id,
    wo.root_org_name,
    ISNULL(dc.covered_employees, 0) AS covered_employees,
    ISNULL(dt.total_employees, 0) AS total_employees,
    CAST(
        100.0 * ISNULL(dc.covered_employees, 0)
        / NULLIF(ISNULL(dt.total_employees, 0), 0)
        AS DECIMAL(5, 2)
    ) AS coverage_rate_percent
FROM WeekOrg AS wo
LEFT JOIN DepartmentTotals AS dt
    ON dt.week_start = wo.week_start
   AND dt.root_org_id = wo.root_org_id
LEFT JOIN DepartmentCoverage AS dc
    ON dc.week_start = wo.week_start
   AND dc.root_org_id = wo.root_org_id
ORDER BY wo.week_start, wo.root_org_id
OPTION (MAXRECURSION 32767);


-- 人員黏著度統計：工作日活躍（每日）
WITH DateBounds AS (
    SELECT
        MIN(CAST(e.InDate AS DATE)) AS min_in_date,
        MAX(CAST(ISNULL(e.OutDate, CAST(GETDATE() AS DATE)) AS DATE)) AS max_out_date
    FROM empbas_app AS e WITH (NOLOCK)
),
ActiveBounds AS (
    SELECT
        MIN(CAST(a.ActivateTime AS DATE)) AS min_active_date,
        MAX(CAST(a.ActivateTime AS DATE)) AS max_active_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
),
Boundaries AS (
    SELECT
        COALESCE(ab.min_active_date, db.min_in_date, CAST(GETDATE() AS DATE)) AS min_date,
        COALESCE(ab.max_active_date, db.max_out_date, CAST(GETDATE() AS DATE)) AS max_date
    FROM DateBounds AS db
    CROSS JOIN ActiveBounds AS ab
),
Calendar AS (
    SELECT
        0 AS day_index,
        b.min_date AS calendar_date,
        b.max_date
    FROM Boundaries AS b
    UNION ALL
    SELECT
        day_index + 1,
        DATEADD(DAY, 1, calendar_date),
        max_date
    FROM Calendar
    WHERE DATEADD(DAY, 1, calendar_date) <= max_date
),
WorkingDays AS (
    SELECT calendar_date
    FROM Calendar
    WHERE DATEPART(WEEKDAY, calendar_date) BETWEEN 2 AND 6
),
DailyUsage AS (
    SELECT
        CAST(a.ActivateTime AS DATE) AS usage_date,
        COUNT(DISTINCT a.EmpId) AS active_users
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
    INNER JOIN empbas_app AS e WITH (NOLOCK)
        ON e.EmpId = a.EmpId
       AND e.InDate <= a.ActivateTime
       AND (e.OutDate IS NULL OR e.OutDate > a.ActivateTime)
    WHERE DATEPART(WEEKDAY, a.ActivateTime) BETWEEN 2 AND 6
    GROUP BY CAST(a.ActivateTime AS DATE)
),
DailyEmployment AS (
    SELECT
        d.calendar_date,
        COUNT(DISTINCT CASE WHEN e.EmpId IS NOT NULL THEN e.EmpId END) AS total_employees
    FROM WorkingDays AS d
    LEFT JOIN empbas_app AS e WITH (NOLOCK)
        ON e.InDate <= d.calendar_date
       AND (e.OutDate IS NULL OR e.OutDate > d.calendar_date)
    GROUP BY d.calendar_date
)
SELECT
    d.calendar_date AS stat_date,
    ISNULL(u.active_users, 0) AS active_users,
    ISNULL(t.total_employees, 0) AS total_employees,
    CAST(
        100.0 * ISNULL(u.active_users, 0)
        / NULLIF(ISNULL(t.total_employees, 0), 0)
        AS DECIMAL(5, 2)
    ) AS active_rate_percent
FROM WorkingDays AS d
LEFT JOIN DailyUsage AS u
    ON u.usage_date = d.calendar_date
LEFT JOIN DailyEmployment AS t
    ON t.calendar_date = d.calendar_date
ORDER BY d.calendar_date
OPTION (MAXRECURSION 32767);


-- 人員啟用率：新人當月啟用率
WITH NewHires AS (
    SELECT
        e.EmpId,
        DATEFROMPARTS(YEAR(e.InDate), MONTH(e.InDate), 1) AS hire_month,
        EOMONTH(e.InDate) AS month_end
    FROM empbas_app AS e WITH (NOLOCK)
    WHERE e.InDate IS NOT NULL
),
FirstActivation AS (
    SELECT
        a.EmpId,
        MIN(CAST(a.ActivateTime AS DATE)) AS first_activate_date
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
    GROUP BY a.EmpId
)
SELECT
    nh.hire_month,
    COUNT(*) AS new_hires,
    COUNT(CASE
              WHEN fa.first_activate_date IS NOT NULL
               AND fa.first_activate_date <= nh.month_end THEN 1
          END) AS activated_within_month,
    CAST(
        100.0 * COUNT(CASE
                          WHEN fa.first_activate_date IS NOT NULL
                           AND fa.first_activate_date <= nh.month_end THEN 1
                      END)
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(5, 2)
    ) AS activation_rate_percent
FROM NewHires AS nh
LEFT JOIN FirstActivation AS fa
    ON fa.EmpId = nh.EmpId
GROUP BY nh.hire_month, nh.month_end
ORDER BY nh.hire_month;


-- 人員留存率：月度留存（前月對比）
WITH MonthlyActive AS (
    SELECT DISTINCT
        DATEFROMPARTS(YEAR(a.ActivateTime), MONTH(a.ActivateTime), 1) AS active_month,
        a.EmpId
    FROM UTLife_DailyActivateUser AS a WITH (NOLOCK)
    INNER JOIN empbas_app AS e WITH (NOLOCK)
        ON e.EmpId = a.EmpId
       AND e.InDate <= a.ActivateTime
       AND (e.OutDate IS NULL OR e.OutDate > a.ActivateTime)
),
CurrentMonth AS (
    SELECT
        ma.active_month,
        COUNT(DISTINCT ma.EmpId) AS active_users
    FROM MonthlyActive AS ma
    GROUP BY ma.active_month
),
Retention AS (
    SELECT
        curr.active_month,
        COUNT(DISTINCT CASE WHEN prev.EmpId IS NOT NULL THEN curr.EmpId END) AS retained_users
    FROM MonthlyActive AS curr
    LEFT JOIN MonthlyActive AS prev
        ON prev.EmpId = curr.EmpId
       AND prev.active_month = DATEADD(MONTH, -1, curr.active_month)
    GROUP BY curr.active_month
),
PrevMonthUsers AS (
    SELECT
        DATEADD(MONTH, 1, active_month) AS active_month,
        COUNT(DISTINCT EmpId) AS prev_active_users
    FROM MonthlyActive
    GROUP BY active_month
)
SELECT
    c.active_month,
    c.active_users,
    ISNULL(p.prev_active_users, 0) AS previous_month_active_users,
    ISNULL(r.retained_users, 0) AS retained_users,
    CAST(
        100.0 * ISNULL(r.retained_users, 0)
        / NULLIF(ISNULL(p.prev_active_users, 0), 0)
        AS DECIMAL(5, 2)
    ) AS retention_rate_percent
FROM CurrentMonth AS c
LEFT JOIN Retention AS r
    ON r.active_month = c.active_month
LEFT JOIN PrevMonthUsers AS p
    ON p.active_month = c.active_month
ORDER BY c.active_month;


-- 訊息量統計：每週工作日訊息數總計
WITH DateBounds AS (
    SELECT
        MIN(CAST(e.InDate AS DATE)) AS min_in_date,
        MAX(CAST(ISNULL(e.OutDate, CAST(GETDATE() AS DATE)) AS DATE)) AS max_out_date
    FROM empbas_app AS e WITH (NOLOCK)
),
MessageBounds AS (
    SELECT
        MIN(CAST(m.Timestamp AS DATE)) AS min_msg_date,
        MAX(CAST(m.Timestamp AS DATE)) AS max_msg_date
    FROM LineGPT_Messages AS m WITH (NOLOCK)
),
Boundaries AS (
    SELECT
        COALESCE(mb.min_msg_date, db.min_in_date, CAST(GETDATE() AS DATE)) AS min_date,
        COALESCE(mb.max_msg_date, db.max_out_date, CAST(GETDATE() AS DATE)) AS max_date
    FROM DateBounds AS db
    CROSS JOIN MessageBounds AS mb
),
WeekCalendar AS (
    SELECT
        0 AS week_index,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.min_date) % 7, b.min_date) AS week_start,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.max_date) % 7, b.max_date) AS max_week_start
    FROM Boundaries AS b
    UNION ALL
    SELECT
        week_index + 1,
        DATEADD(WEEK, 1, week_start),
        max_week_start
    FROM WeekCalendar
    WHERE DATEADD(WEEK, 1, week_start) <= max_week_start
),
Weeks AS (
    SELECT
        wc.week_start,
        DATEADD(DAY, 6, wc.week_start) AS week_end,
        DATEPART(ISO_WEEK, wc.week_start) AS iso_week,
        DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)) AS iso_year,
        CONCAT(
            DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)),
            '-W',
            RIGHT('00' + CAST(DATEPART(ISO_WEEK, wc.week_start) AS VARCHAR(2)), 2)
        ) AS week_label
    FROM WeekCalendar AS wc
),
WeeklyMessages AS (
    SELECT
        w.week_start,
        COUNT(*) AS message_count
    FROM Weeks AS w
    LEFT JOIN LineGPT_Messages AS m WITH (NOLOCK)
        ON m.Timestamp >= w.week_start
       AND m.Timestamp < DATEADD(DAY, 7, w.week_start)
       AND DATEPART(WEEKDAY, m.Timestamp) BETWEEN 2 AND 6
    LEFT JOIN empbas_app AS e WITH (NOLOCK)
        ON e.EmpId = m.SendEmpid
       AND e.InDate <= m.Timestamp
       AND (e.OutDate IS NULL OR e.OutDate >= m.Timestamp)
    GROUP BY w.week_start
)
SELECT
    w.iso_year,
    w.iso_week,
    w.week_label,
    w.week_start AS stat_date,
    ISNULL(wm.message_count, 0) AS message_count
FROM Weeks AS w
LEFT JOIN WeeklyMessages AS wm
    ON wm.week_start = w.week_start
ORDER BY w.week_start
OPTION (MAXRECURSION 32767);


-- 訊息量統計：每週工作日人均訊息數
WITH DateBounds AS (
    SELECT
        MIN(CAST(e.InDate AS DATE)) AS min_in_date,
        MAX(CAST(ISNULL(e.OutDate, CAST(GETDATE() AS DATE)) AS DATE)) AS max_out_date
    FROM empbas_app AS e WITH (NOLOCK)
),
MessageBounds AS (
    SELECT
        MIN(CAST(m.Timestamp AS DATE)) AS min_msg_date,
        MAX(CAST(m.Timestamp AS DATE)) AS max_msg_date
    FROM LineGPT_Messages AS m WITH (NOLOCK)
),
Boundaries AS (
    SELECT
        COALESCE(mb.min_msg_date, db.min_in_date, CAST(GETDATE() AS DATE)) AS min_date,
        COALESCE(mb.max_msg_date, db.max_out_date, CAST(GETDATE() AS DATE)) AS max_date
    FROM DateBounds AS db
    CROSS JOIN MessageBounds AS mb
),
WeekCalendar AS (
    SELECT
        0 AS week_index,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.min_date) % 7, b.min_date) AS week_start,
        DATEADD(DAY, -DATEDIFF(DAY, 0, b.max_date) % 7, b.max_date) AS max_week_start
    FROM Boundaries AS b
    UNION ALL
    SELECT
        week_index + 1,
        DATEADD(WEEK, 1, week_start),
        max_week_start
    FROM WeekCalendar
    WHERE DATEADD(WEEK, 1, week_start) <= max_week_start
),
Weeks AS (
    SELECT
        wc.week_start,
        DATEADD(DAY, 6, wc.week_start) AS week_end,
        DATEPART(ISO_WEEK, wc.week_start) AS iso_week,
        DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)) AS iso_year,
        CONCAT(
            DATEPART(YEAR, DATEADD(DAY, 3, wc.week_start)),
            '-W',
            RIGHT('00' + CAST(DATEPART(ISO_WEEK, wc.week_start) AS VARCHAR(2)), 2)
        ) AS week_label
    FROM WeekCalendar AS wc
),
WeeklyMessageTotals AS (
    SELECT
        w.week_start,
        COUNT(*) AS message_count
    FROM Weeks AS w
    LEFT JOIN LineGPT_Messages AS m WITH (NOLOCK)
        ON m.Timestamp >= w.week_start
       AND m.Timestamp < DATEADD(DAY, 7, w.week_start)
       AND DATEPART(WEEKDAY, m.Timestamp) BETWEEN 2 AND 6
    LEFT JOIN empbas_app AS e WITH (NOLOCK)
        ON e.EmpId = m.SendEmpid
       AND e.InDate <= m.Timestamp
       AND (e.OutDate IS NULL OR e.OutDate >= m.Timestamp)
    GROUP BY w.week_start
),
WeeklyEmployment AS (
    SELECT
        w.week_start,
        COUNT(DISTINCT CASE WHEN e.EmpId IS NOT NULL THEN e.EmpId END) AS total_employees
    FROM Weeks AS w
    LEFT JOIN empbas_app AS e WITH (NOLOCK)
        ON e.InDate <= w.week_end
       AND (e.OutDate IS NULL OR e.OutDate > w.week_start)
    GROUP BY w.week_start
)
SELECT
    w.iso_year,
    w.iso_week,
    w.week_label,
    w.week_start AS stat_date,
    ISNULL(mt.message_count, 0) AS message_count,
    ISNULL(we.total_employees, 0) AS total_employees,
    CAST(
        1.0 * ISNULL(mt.message_count, 0)
        / NULLIF(ISNULL(we.total_employees, 0), 0)
        AS DECIMAL(10, 2)
    ) AS avg_messages_per_employee
FROM Weeks AS w
LEFT JOIN WeeklyMessageTotals AS mt
    ON mt.week_start = w.week_start
LEFT JOIN WeeklyEmployment AS we
    ON we.week_start = w.week_start
ORDER BY w.week_start
OPTION (MAXRECURSION 32767);


-- 訊息量統計：訊息分布分析（20/60/20）
WITH WeeklyUserMessages AS (
    SELECT
        DATEADD(DAY, -DATEDIFF(DAY, 0, CAST(m.Timestamp AS DATE)) % 7, CAST(m.Timestamp AS DATE)) AS week_start,
        DATEPART(ISO_WEEK, CAST(m.Timestamp AS DATE)) AS iso_week,
        DATEPART(YEAR, DATEADD(DAY, 3, CAST(m.Timestamp AS DATE))) AS iso_year,
        m.SendEmpid AS emp_id,
        COUNT(*) AS message_count
    FROM LineGPT_Messages AS m WITH (NOLOCK)
    INNER JOIN empbas_app AS e WITH (NOLOCK)
        ON e.EmpId = m.SendEmpid
       AND e.InDate <= m.Timestamp
       AND (e.OutDate IS NULL OR e.OutDate >= m.Timestamp)
    WHERE DATEPART(WEEKDAY, m.Timestamp) BETWEEN 2 AND 6
    GROUP BY
        DATEADD(DAY, -DATEDIFF(DAY, 0, CAST(m.Timestamp AS DATE)) % 7, CAST(m.Timestamp AS DATE)),
        DATEPART(ISO_WEEK, CAST(m.Timestamp AS DATE)),
        DATEPART(YEAR, DATEADD(DAY, 3, CAST(m.Timestamp AS DATE))),
        m.SendEmpid
),
RankedMessages AS (
    SELECT
        wum.*,
        ROW_NUMBER() OVER (
            PARTITION BY wum.iso_year, wum.iso_week
            ORDER BY wum.message_count DESC
        ) AS rn,
        COUNT(*) OVER (
            PARTITION BY wum.iso_year, wum.iso_week
        ) AS user_count,
        SUM(wum.message_count) OVER (
            PARTITION BY wum.iso_year, wum.iso_week
        ) AS total_messages
    FROM WeeklyUserMessages AS wum
),
Segmented AS (
    SELECT
        rm.iso_year,
        rm.iso_week,
        rm.week_start,
        CASE
            WHEN CAST(rm.rn - 1 AS FLOAT) / NULLIF(rm.user_count, 0) < 0.2 THEN N'前20%'
            WHEN CAST(rm.rn - 1 AS FLOAT) / NULLIF(rm.user_count, 0) < 0.8 THEN N'中間60%'
            ELSE N'後20%'
        END AS segment,
        rm.message_count,
        rm.total_messages,
        rm.user_count
    FROM RankedMessages AS rm
)
SELECT
    s.iso_year,
    s.iso_week,
    CONCAT(
        s.iso_year,
        '-W',
        RIGHT('00' + CAST(s.iso_week AS VARCHAR(2)), 2)
    ) AS week_label,
    s.week_start AS stat_date,
    s.segment,
    COUNT(*) AS users_in_segment,
    SUM(s.message_count) AS message_count,
    CAST(
        100.0 * SUM(s.message_count)
        / NULLIF(MAX(s.total_messages), 0)
        AS DECIMAL(5, 2)
    ) AS message_share_percent,
    CAST(
        100.0 * COUNT(*)
        / NULLIF(MAX(s.user_count), 0)
        AS DECIMAL(5, 2)
    ) AS user_share_percent
FROM Segmented AS s
GROUP BY
    s.iso_year,
    s.iso_week,
    s.week_start,
    s.segment
ORDER BY
    s.iso_year,
    s.iso_week,
    s.segment;
