from __future__ import annotations

from core.result import TaskResult
from examples.sample_data_generator import generate_sample_data
from tasks.base_task import BaseTask


class GenerateSampleDataTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        path = generate_sample_data(symbol=kwargs.get("symbol", "601088.SH"), timeframe=kwargs.get("timeframe", "1d"))
        return TaskResult("VALID", f"示例数据已生成：{path}", artifacts={"data_path": str(path)})
