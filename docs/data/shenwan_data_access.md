# 申万官方数据获取与本地原文件 fallback

- 诊断日期：2026-09-20
- 范围：只处理可信获取、原文件保存和可重复解析
- 当前结论：**在线 TLS 被申万服务端不完整证书链阻断；使用官方文件 fallback**
- LEVEL B 准入：**未通过，且本文档不授予准入**

## 1. TLS 诊断证据

容器 `quant-research` 的 Python 使用 OpenSSL 3.6.4。默认 Python CA 路径为
`/opt/conda/ssl/cert.pem`，`certifi.where()` 与 requests 的 CA 路径为
`/opt/conda/lib/python3.12/site-packages/certifi/cacert.pem`。两者内容哈希相同：

```text
9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f
```

系统 CA bundle 为 `/etc/ssl/certs/ca-certificates.crt`，SHA256：

```text
9481fcd95f41b221f02f14d896535fe500bec539bc563c4cdca1acee483a8bdd
```

诊断结果：

| 检查 | 结果 |
|---|---|
| DNS | `www.swsresearch.com` 解析为 `202.122.119.203` |
| TCP 443 | 可连接 |
| requests + certifi | `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate` |
| requests + 系统 CA 环境变量 | 同样失败 |
| curl + 系统 CA | code 60，OpenSSL verify result 20 |
| curl + Conda CA | code 60，OpenSSL verify result 20 |
| openssl `s_client -showcerts` | 只收到 1 张叶证书，verify error 20 |

服务端叶证书信息：

```text
subject = C=CN, ST=上海市, O=上海申银万国证券研究所有限公司,
          CN=*.swsresearch.com
issuer  = C=US, O=DigiCert, Inc.,
          CN=GeoTrust G2 TLS CN RSA4096 SHA256 2022 CA1
valid   = 2026-05-12 through 2026-11-26
```

服务端没有发送 issuer 对应的中间证书。DNS、TCP 和证书有效期均正常；容器也没有
`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`REQUESTS_CA_BUNDLE`、
`SSL_CERT_FILE` 等覆盖变量。证书 subject/issuer 没有出现企业代理或 VPN CA。
因此根因属于 **申万服务端证书链不完整**，不是系统 CA 损坏、certifi 路径错误、
代理 CA 未导入或 DNS 故障。

没有执行以下操作：

- 没有使用 `verify=False`；
- 没有向系统或 Conda trust store 导入证书；
- 没有把未知证书设为根 CA；
- 没有修改 AKShare；
- 没有重建镜像或改变依赖。

## 2. 当前 AKShare 1.18.88 的实际行为

以容器内安装源码为准：

- `stock_industry_clf_hist_sw()` 直接用 requests 请求官方
  `StockClassifyUse_stock.xls`，当前因不完整证书链失败；
- `index_hist_sw()` 内部硬编码 `verify=False`，不符合本项目 TLS 约束，
  本轮没有调用，也不能据此认定在线接口可用；
- TLS 没有恢复，因此没有伪造接口字段、条数、日期范围或分类版本结果。

## 3. 官方原文件 fallback

本地 raw 目录固定为：

```text
data/raw/shenwan/
```

该目录已被仓库根 `.gitignore` 排除。允许通过正常浏览器下载官方公开文件后，
原样放入目录；不需要 Cookie、账号或金融账户信息。当前至少支持：

```text
https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls
```

初始化 manifest：

```bash
docker compose exec quant-research \
  python scripts/data/import_shenwan_official.py init-manifest
```

放入原文件后登记。下载时间或分类版本没有证据时不要猜测，省略参数即保存
为 `null`：

```bash
docker compose exec quant-research \
  python scripts/data/import_shenwan_official.py register-classification \
  --retrieved-at 2026-09-20T10:00:00+08:00 \
  --classification-version '有官方证据的版本' \
  --notes '正常浏览器从上述官方公开 URL 下载'
```

`manifest.json` 对每个文件记录：`provider`、`source_url`、`retrieved_at`、
`original_filename`、`sha256`、`classification_version`、`notes`。
重复文件名不会自动覆盖；文件被改动后 SHA256 校验会失败。
后续取得的其他申万官方原文件使用通用 `register --filename ... --source-url ...`
登记；来源仍必须是 `swsresearch.com` 的 HTTPS URL。

校验与解析：

```bash
docker compose exec quant-research \
  python scripts/data/import_shenwan_official.py verify

docker compose exec quant-research \
  python scripts/data/import_shenwan_official.py parse-classification \
  --output data/processed/shenwan/stock_classification.csv
```

下载与解析完全分离。解析器只读取 raw 文件，输出不得写回 raw 目录。

## 4. PIT 语义与准入阻断

canonical 分类结果保留：

```text
symbol, sector_code, sector_name,
effective_from, effective_to, available_at,
source_updated_at, classification_version,
source_provider, source_url, source_retrieved_at,
source_filename, source_sha256
```

官方表的“计入日期”映射为 `effective_from`。“更新日期”只映射为
`source_updated_at`，**不得冒充 publication timing / available_at**。
没有证据的 `effective_to`、`available_at` 和 `classification_version` 保持
`null`；下载时间未知时 `source_retrieved_at` 也保持 `null`。
`--require-level-b-admission` 会在这些字段缺失时拒绝输出。

即使将来能够下载，仍需独立证明 classification version、历史生效区间、
publication timing、指数历史定义与回算政策、OHLCVA 完整性及历史 ETF mapping。
当前分类版本未知、PIT publication evidence 缺失，所以正式 LEVEL B 继续被阻断。

## 5. 网络测试

默认 pytest 完全离线。申万网络探针同时标记 `integration` 和 `network`，还要求
显式设置 `RUN_SHENWAN_NETWORK_TESTS=1`。探针始终使用 requests 的严格 TLS
校验；服务端证书链修复前，显式运行该探针应失败，而不是被当作成功。
