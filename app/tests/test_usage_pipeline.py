"""UsageStatsPipeline 的單元測試。"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.etl.pipelines.usage_pipeline import UsageStatsPipeline


class DummyUsagePipeline(UsageStatsPipeline):
    """覆寫 extract 以提供測試資料。"""

    def __init__(self) -> None:
        super().__init__(sql_source=None, duck_client=None, target_date=date(2024, 9, 1))

    def extract(self):  # type: ignore[override]
        """回傳固定測試資料集。"""

        employees = pd.DataFrame(
            {
                "EmpNo": ["E01", "E02"],
                "UnitId": ["U1", "U2"],
                "ClassOrg": ["A", "B"],
            }
        )
        daily_active = pd.DataFrame(
            {
                "ActiveDate": ["2024-08-30", "2024-08-31", "2024-08-30"],
                "UnitId": ["U1", "U1", "U2"],
                "EmpNo": ["E01", "E01", "E02"],
            }
        )
        messages = pd.DataFrame(
            {
                "MsgDate": ["2024-08-30", "2024-08-30"],
                "SenderEmpNo": ["E01", "E02"],
                "UnitId": ["U1", "U2"],
                "MessageCount": [5, 10],
            }
        )
        device = pd.DataFrame(
            {
                "EmpNo": ["E01", "E02"],
                "FirstInstallDate": ["2024-07-01", "2024-07-05"],
            }
        )
        return {
            "employees": employees,
            "daily_active": daily_active,
            "messages": messages,
            "device": device,
        }


def test_transform_generate_expected_keys() -> None:
    """確認 transform 會輸出預期的資料表鍵值。"""

    pipeline = DummyUsagePipeline()
    raw = pipeline.extract()
    processed = pipeline.transform(raw)

    assert set(processed.keys()) == {
        "usage_weekly",
        "daily_active",
        "message_daily",
        "message_distribution",
        "message_leaderboard",
        "activation_monthly",
    }

    assert not processed["usage_weekly"].empty
    assert not processed["message_daily"].empty
    assert not processed["message_leaderboard"].empty


