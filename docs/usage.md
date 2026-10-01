# Closed SQLite schema snapshots / SQLite 结构快照

```sh
sqlite-schema-atlas current.db --html schema.html --json schema.json
sqlite-schema-atlas current.db --before previous.db --html diff.html --json diff.json
```

Only trusted, closed, checkpointed local snapshots up to 64 MiB. Nonempty `-wal`/`-journal` sidecars
reject. Inputs open with mode=ro/immutable, query_only and trusted_schema=OFF; no extension loading.
No rows are selected. Table/column names, types, PK positions, default *presence*, and foreign keys
are exported. SQL text/default values are NOT exported; DDL SHA-256 allows structural change tracking.
Formatting alone can change the hash. No relationship graph layout or migration SQL generation.

Virtual tables are listed but not introspected. Their ordinary shadow tables may be listed. Views
are not executed. Maximum 2,000 schema objects / 10,000 column and FK details / 1 MiB DDL each;
query instruction budget enforced. System `sqlite_` objects excluded. Schema inventory has zero
findings by definition; comparison findings count added/removed/DDL-changed objects.

先关闭并 checkpoint 源数据库，再使用可信快照。不能用本工具替代一致性备份工具或数据库安全沙箱。
没有读取到差异不等于迁移安全。程序不会自动 checkpoint 或修改原文件。
