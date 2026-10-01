# sqlite-schema-atlas

只读检查已关闭 SQLite 快照的结构，并比较两版。

Python 3.10+，零运行时依赖，本地 alpha；没有独立用户验证，不宣称生产可用。

从本仓库 GitHub Release v0.1.0 下载 wheel，在虚拟环境安装：

```sh
python -m pip install /path/to/sqlite_schema_atlas-0.1.0-py3-none-any.whl
sqlite-schema-atlas --demo --html synthetic-report.html --json synthetic-report.json
```

打开 HTML，无需联网。例子是合成数据，不是真实客户案例。
暂未发布到 PyPI，不要把 PyPI 上可能同名的包当成本项目。
源码可 `python -m pip install .`；真实输入见 docs/usage.md 和 --help。

边界：Trusted closed database snapshots only. Reject nonempty WAL/journal files. No row data or SQL defaults exported. Virtual tables not introspected. Not a database-file security sandbox or migration planner.

不会上传、遥测、执行输入或自动修改原文。报告可能含字段/路径/结构名称/字幕原文，分享前需核查。
HTML 每表最多预览 1,000 行，完整结果见 JSON。输出仅写新文件，不覆盖已有内容。
退出 0 表示分析完成而非安全保证；--fail-on-findings 下有发现退出 1；格式/上限/输出错误退出 2。
测试：`python -m unittest discover -s tests -v`；构建后运行 `python scripts/smoke.py` 验证安装产物。
MIT 许可，反馈只使用合成输入。完整边界与相邻工具链接见英文 README。

### Windows application-control fallback

If Windows blocks the pip-generated console `.exe`, keep your security policy enabled and use the equivalent installed module:

```sh
python -m sqlite_schema_atlas --demo
```

## Synthetic output preview

![Synthetic report; no private input](docs/preview.png)
