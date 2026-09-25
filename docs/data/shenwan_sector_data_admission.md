# 申万二级行业数据接入与准入审计

审计日期：2026-09-23。代码分支 `experiment/shenwan-sector-data-integration`。
数据仅用于申万固定行业指数体系的研究准备；没有运行策略、回测、ETF 映射或 OOS 分区。

## 来源、raw 清单与不可变性

来源为申万研究公开的分类 XLS、`index_publish/current` 二级行业目录和
`index_publish/trend` 日线响应。原始文件位于 `data/raw/shenwan/`，
历史行情清单位于 `data/manifests/shenwan_sector_history_manifest.json`。
导入脚本只读 raw，只写 `data/processed/shenwan/`；全部 raw/processed 均由
`.gitignore` 排除。没有在本次任务重新下载任何行情。

| 资产 | 文件数 | SHA256 / 指纹 |
|---|---:|---|
| 股票分类 | 1 | `StockClassifyUse_stock.xls`: `1a181c4a7aa1db22ea3c52233221d9d70b731ed6cb0fd7c9bbc80f6b0c066742` |
| 二级目录原始分页 | 3 | 见下表 |
| 二级目录整理副本 | 1 | `sws_index_catalog_L2.jsonl`: `073220802fdac63704ccf26b6a175196031f9109600635d2aab954cec988d025`；逐条与官方分页核对 |
| 二级行业日线 | 124 | 每份文件的 SHA256、URL、日期范围和行数见 `data/manifests/shenwan_sector_history_manifest.json`，导入时逐一重新计算并对照 |
| 日线 manifest | 1 | `45fd1257ad9ecf78fe608029cdb48ca2948194a42d2e15d56b79d06987ed76b4` |

| 官方二级目录页 | SHA256 |
|---|---|
| `sws_index_catalog_L2_page1.json` | `3a767f569a56d6ae0703bf8040978e28bbf713426e4f23eeb971738cf058208c` |
| `sws_index_catalog_L2_page2.json` | `472875731990bfd504daf94781fa512241d49cd6652ca8bbb53dbfa899ad0726` |
| `sws_index_catalog_L2_page3.json` | `171444c35faa985a3652551ea373535bd65461bda2704eaf5f7b0f676b86599c` |

目录 3 页 `count=124`，页间 `next/previous` 链含官方 `indextype=二级行业` 参数，
124 个代码唯一、名称完整，Level-2 判定依据是这条请求/响应链，而非股票分类表的
553 个行业代码。目录源 URL 和取得时间由既有采集脚本及行情 manifest 重建；
API 响应本身没有逐页下载时间字段，此来源限制保留在 admission metadata。
原始目录还含一级行业文件，本轮仅审计并转换二级集合，不把一级文件混入快照。

完整 124 份历史原文件的 SHA256 清单：

| sector_code | raw SHA256 |
|---|---|
| `801012` | `56ea1a2aeb4fdd16bd25b65dfe7b5f1b456dbbc6992eba8892d64aa7bf635bef` |
| `801014` | `e2115c25b7cd45f6b5661faa6ecd02f35b348a218f0151e09c1fc9cd8d0eb3f5` |
| `801015` | `352806d7fd977db8acfabd733f3a5e44f1eed2adc7dacdd5e8f1b40e6ee81ada` |
| `801016` | `1f1a081dceb57709c6e9b51c090eaf38a93d757a122bd8648a5e4600af6e34ba` |
| `801017` | `911f38e1fe3cabdf18b13ac14ff9d150a02178e9b6c42d66cd6586ad5752413e` |
| `801018` | `604c3973fa2edd74e8029946e362a4d1c1ef1ec0e022faa0ecb19e288b268b60` |
| `801032` | `e172c6e362287fd1a1d49f72473a7d7ed40e724706b569ec4e421a98743355ec` |
| `801033` | `569e402da3008306e487138ee84b30ca6d67d50b12e59029248d649e0d2afbdb` |
| `801034` | `370de1ef835681148d92c7181f8f7088dca66ffc13133543db0819b0b074c373` |
| `801036` | `f038be101fee2c935aa4720c3ec6df701258408dd35630c5444738f241e158d6` |
| `801037` | `e81eef0881ed7fe53a1d17a5232d6a08fff4d047a43f6a232e9dbf590a1b5871` |
| `801038` | `2c34d1a448876f5726ea1eab65543badd567231dbb29667c3172f090a7bf63dd` |
| `801039` | `b6153d800b4a23fea89d1a6e1752effbd14b5fe202f2c6ba93d454da5a509b7c` |
| `801043` | `ec0c610607c9caaf781c414c44e9cecb7b4a593351dd5afdbe79ee1216ee0201` |
| `801044` | `66c947a7f63b9cb2c15593b6a4c4ed80ef0aeb4bd400e79b8511351d8f019131` |
| `801045` | `58eb9a455a1477c45cdb4d5bb634be332628327956c2547397eb97557632936b` |
| `801051` | `779b6c8cbd11a74c75201e61fa377db6e5a26a3c31ae8a7cc5cb072cafcef68a` |
| `801053` | `8121bf6c618019d85f16d04c5e187298984c795781d266ee1574645adb818bb9` |
| `801054` | `011d5790ff0051b37b5a86b4652e553e0415b16caf2aac6467dbffaa8b77b062` |
| `801055` | `ba6c390820feeabfa120449da6e2dafb03c2e0decf864704cde919998f1018fc` |
| `801056` | `fcdbd63799dbc1040e312a8e380280846fd819a8d0a433c4d584b1dc23d914e4` |
| `801072` | `5e56cbd1af60b6362e68d19f0be8b9cc75a1df3539ee34615f15bde3a4ea24f0` |
| `801074` | `d656b225ac597bd7a8b599a137fbf0df0a728523eb39f9fff67491de3c73b98e` |
| `801076` | `68da7e111529f02258187bd3ae3aec3205f09da7fd66c4fbf86e165c753a5682` |
| `801077` | `5d68ad09c4beaf49872848fd672e2e79bea530b0e6fc51044b79d8a7369aa7e7` |
| `801078` | `c93c60161ea10e30a1f600a28b318a3bbd682af923d120025881c1b3ee5356eb` |
| `801081` | `462d478307206656a5cc348633fa5381598bb55b807bb3f63483616d4bf297fb` |
| `801082` | `dbd7c28604d534454be413890b18cb8150596b4c837ce401fb60e37cf4aca79e` |
| `801083` | `1311f5ade632c53d87df083c284cb3e98f230c29f6d48f32f9027703e3ad92c2` |
| `801084` | `83a8390b447bee853480f5dff5f44194f1c374c18748c7b6f640686a83a5c2f7` |
| `801085` | `aebf608b28d792dab1a52da5cdbd659907e6ac3fdb6ba9ff796febcd29865202` |
| `801086` | `ddcd2e04bcfaed92e2162db1694ff435fddd3cb0b5fafb64ee31fd6bf9871a2d` |
| `801092` | `0b27e916cc631e573af9391872698ae4b15c4f2ac7bf8d64f988e09bb302e9d4` |
| `801093` | `4a0f28a05fbc76d1fb5cc61dff31f171fc6a1d104e3ca5c620c9353c53095006` |
| `801095` | `c2686c3f99321d8cc55d720816395e665ac6a9cf481282b1d9d19faf1689fbfc` |
| `801096` | `77d6067bd3cc382fb2926cb6ed4bfc87c389af51c4fd6ca185259add11e2e0fe` |
| `801101` | `a5174d48ef9e1bad593a0b2ac543c8c7b335924215f4b113d671b19c0cc3d838` |
| `801102` | `821e8a9450845c34aa074ff247238dd918b0f06b1ad631c7f3a1fba8ad63d04d` |
| `801103` | `bc73341f3855d75f5e168f281ecc8e8746820e01efd88c0fac9a8a51f7624f73` |
| `801104` | `1001222fba72a43db85e6490664d3b765b0e836b6ad568684546bd9da95260a6` |
| `801111` | `670d50cf2b353fd1634b6eb61156707487bce98aff7aa276c8a6f82693ad626e` |
| `801112` | `6eafd5de1c7ab76643cff5b574939ceb942c54fc5f3d55115107d52891bd9dbf` |
| `801113` | `e739239ec7fac67554c686de34cee95a711aa5491196fc9d7a6277411f1fa055` |
| `801114` | `3f9819584fc42d28ba9d5004dac6a30ba620fe6d2bae304b660991e188ce06fe` |
| `801115` | `48288efbfc8bac521706511ea4ea6798253d44da8e3d940fe39b4daa9a5e6b29` |
| `801116` | `31af2cade8b0fca377eac474efbeebb74eb6592234fa77554c35f42fcd26aced` |
| `801124` | `6eed87913055058d2b2b9222e673c2dcc28c317da25cde560b8d51a7774cc03b` |
| `801125` | `e2b3aeefc3c75cccdfb754461d9d72ea3268f8554c64f72662285615ffb4104d` |
| `801126` | `a987bed5b6fa20f566ae9bc9b1c75f14525bb6dee6575a547b8df37ef6fe5c99` |
| `801127` | `796804597d72f275a2fc7aad96e1b65311dd05eda27904ea2ac72d8526e1d8b8` |
| `801128` | `394c8c7339a56d5f13e99e3ecd2faed93bf3efe782a91789cd02d4c130689f6b` |
| `801129` | `fc0e35ec58b7293648895cb1afd94515c7be255faaa41eaf3cfb112e6dac22ea` |
| `801131` | `f3453e64188d92f268a3075bcc397e33b98766b82362d15196f010f77789064f` |
| `801132` | `dc04601934f9bdbcd75941f37516bb4633fa9540a8e61785996b29e902751a44` |
| `801133` | `329bd1fef1dff150fb0a664f8b43651110a9b7585633a2c5c190235b64ef7e34` |
| `801141` | `4f7268bb61f336215c75642545cc53606a2bf8f6ea865dcbb20af7f2d0900919` |
| `801142` | `340d0633866adfd736cf4e0accc94cffe318d6bc0c5ae635b45e221dcff43c33` |
| `801143` | `793c2c83766b1c1b0c6077a110e09ee6d5c981b857d7b6503e04b4f16329ed23` |
| `801145` | `02ccf221ed9db4ff51045a324e50f831969a4cae9895813a46b8051d16ebaef0` |
| `801151` | `2d4869a5f1153aa5ff02688fc282b04d1f31c575ddc317d77feacf57d4be4ba8` |
| `801152` | `2e090ca5b8071ff306bc9c22bbeaa653cc1f53c9e5e675748335e9288607ec8b` |
| `801153` | `32214e08352e7f38f0728bd6d395727ff69de7cbacd5ef6321c88a0a79b0658a` |
| `801154` | `a438fe9729bbb23325106aaf6f8470dbb76cb5d542c171c6e788ac00f380b0c9` |
| `801155` | `f1a36f2384be08d21716d3885b329339d91f3397bdeee3258110fbbe6da38d49` |
| `801156` | `b6f90890341da0b2a19f37264a0196a1d0cda3c68f170ffd4ff7c37205e46f49` |
| `801161` | `59e6634a01741fb6962b98cc1b9f5540bafe88cf933af61a1945424f7f8bc80d` |
| `801163` | `41718556eeeef43da7b02ed30b34d68e844e75933d011c4c5b5c72c8f40c7ea8` |
| `801178` | `0307bbb8839be446cc92dc154857f69aea21e957e924a9c398db9762fd6be3e2` |
| `801179` | `989a4c25c8de4015936fd499a89c82427ab52aafd4ac909ffba5b0c595ea9b58` |
| `801181` | `a21cd079cd2fdda7720ef215aa85798e94d7229b06c41be693984f9dba87e747` |
| `801183` | `0d386a53d267515f23a21dd4d0da037d4cad99581877113690a98bcabd4986a0` |
| `801191` | `084cf00de2a67a49c9e5137c19705ec2c70295cae342170c3af2eedd672e4a6f` |
| `801193` | `8a49c4a5beeed9881a96d3e7542625cc8d0373cf0d37593b652bb986e6dc9197` |
| `801194` | `32e184941b73c3fb799e8f97a769c19e9dab9bb22d04442ee110c9a397ec3a43` |
| `801202` | `b8a85b56ef37302717956a62ab5d6c68ed79c331be901b199d56a8db25516b2d` |
| `801203` | `50d21c4485a0aecf5bef0cc28f87a0d3a64cadf914a12e1d1bd8ffda8b033757` |
| `801204` | `7c8f2b8c76e3f48771b0af4463f8c8145b43188d5739b48ce312394c5d885fdc` |
| `801206` | `09133b47b03be62cfc8fdf5d8d7806dbe0c21b60d91460cdd65b34718003be9d` |
| `801218` | `c679b1ffb93fca9a8552342915e0643d0c2752323cef75ddb01a644a0abb9d36` |
| `801219` | `f7a1940e6ab4ae23faf286068853cd26a51b6c06ef5082cb266e9b74254f153a` |
| `801223` | `9e3dd29172d33a446a0ccdf9962b6d0ff29d6184790101ea0cdd849e242634a0` |
| `801231` | `af92c4cce07a3427655e9528a37a242f334172171433733f89cc17f3ca5a0839` |
| `801711` | `dd264b980dab8cf2e7909d85c4bfc70b26def1631db9a6e69b4d252c5cdec16b` |
| `801712` | `258c7a3ad54eb013df4908dcbbd95c687ab346317a0e61fec77d643b3b77dc03` |
| `801713` | `e461e94b1dd0dd589634864bdf59bad6c09199ef394aa5cd07bbb8315634b072` |
| `801721` | `eb696e0754a9bbfb626d32c142b1940c442e4df39f24b29248981e4ef243f61e` |
| `801722` | `792dacc3cf57e1608089bc3661d77ec74bfdb2d060cad45c68b14643f75b3ebb` |
| `801723` | `2cfe614106461e5a2593d90fdfcce77117fda560d2c86838ff6e4d1e2af190dd` |
| `801724` | `7a31a602e7e2bb1b4e37083473e708a089a6a65d80ccb9d2851b21f48fc9c660` |
| `801726` | `f5f559eec1c7388f588e08d77065c28f8961dd83cbd155dabba7c44fe62d475d` |
| `801731` | `d1de0dc589a1e4453227233eb2f2da93a3e8c11f01e0def2589aa2aa8c27ad0c` |
| `801733` | `48ef1683e0fa83ad2ff0b0cf47412177a3e38b0de0e6ec1b331ee769381e8e3a` |
| `801735` | `196f157bdea975ce2732a081b7bfb5261904b9fece9d3805c050884c0a09f7f3` |
| `801736` | `8282e8c675f1faca86fc73042b843192577ea6b2c284f150fdbb6b84506495f6` |
| `801737` | `e1f9a8145197709440ba784908b56e9c2aa8dd56e0734684c6e6da0d945e9b06` |
| `801738` | `9a5de562683124795aa3e157bdac777dc2ea0d647ac9c1ef744a106f11748211` |
| `801741` | `b1ecaf6898a47fee311c9f2dbb240ddc93d427c815d4a60d0630123e36a07445` |
| `801742` | `fc62d1e4747e3d6a81fe0ac1d07a77fd7a7528feb8cd6aa414a85f6b8fb2cb0e` |
| `801743` | `a10b95f87955554a6de01461d7494b7baf24a4d23dac11abe0ba169202ca49ce` |
| `801744` | `e86e289b4dfab36749b0b1cf899207bed129fc6a419b32def04318bd25d1d9f3` |
| `801745` | `21ac056685befcea04c0683b35379f22f6168926ca3db1fc100f5af8a04dec40` |
| `801764` | `53047dfcb71d40cd938083b2c9233e2d6cbb3c59268496aa2a9467bd89d4416d` |
| `801765` | `fe06737d50a151ec588056ce96893a396db7ddb6e91be3b4880d09d92b0abb75` |
| `801766` | `0916e9bf84a8d1f43d091bb2ad8c3d7a2a98ee9405f16f87e5c607c356c9c6db` |
| `801767` | `cb51c7f6f0d7164808ceb370b8c711fcb532e66688fbf690893ccbaebabe6cd5` |
| `801769` | `c8afdd2f63452f761f436619e65c500f4041102af53f40e26a9eb98f9874fa08` |
| `801782` | `ae58c4745a21009d68ba3b949fe9fe181a953f4145cb738c3fd994fb0cd5c3c9` |
| `801783` | `5e7061918ab0014adca03348d92ba12b8839ced8abd768f30ea0ebfc3b9ff0ed` |
| `801784` | `f48bd3501ac194aceb10b8319c780658a0233fa518417b43513a1530f9f6d930` |
| `801785` | `de270b5a6c022ed7f6a26e958afd6da526229c035755a47a35d409945a91ee02` |
| `801881` | `7a634e14b46cbbd55481ddf0243176b73a3384a02876f6af716ed3eac4cde6b7` |
| `801951` | `7252c4aee5298cc7a42e2dc68743ed1a6902c349137242eb625f81091d472ae1` |
| `801952` | `897999c27374b5035b138db65155577f4d078ce442ede3894fe91fdd02fc441c` |
| `801962` | `335973b9c53ea4f1ab2440c1650d166fc2f5149325072ea7252dc9cb1ea9ae5b` |
| `801963` | `af561a51aa7c37cccee69fc27ea4da051d8efe20b90a16a23dfd94dfff19b9b8` |
| `801971` | `06470ceeb2c90cdd52b48cc0b5910453eaabfec8e5fa022d30b416910f1401aa` |
| `801972` | `df05aae60ff94503e9cd276f302bf597153638f4ebd0c057263ec8f72346ea16` |
| `801981` | `e01e196b9375e5012750dbbb66b6ee49337466812e602c6e9958108315fba547` |
| `801982` | `5fab1b3ac176246bb5ed485d2b9a49ee8c5150ea98b8bff9b97afbeb6b27a37a` |
| `801991` | `3ccd2300b2f53d719517456c6493f1a1764b78581b9c5f1d0cd0904b3e1e34b5` |
| `801992` | `5b0ab6f5e928cf96c4d07a3c55162be0f738efb3a9908ba99364bf0de9402cf7` |
| `801993` | `c6dbd60040b9d4909115ba77c00f961dad543c578344ff24a7852a4fc50dd925` |
| `801994` | `5d6d0af1d0d1304ca28080b6cc6eb6fb8edf55f546b04adb95e319959b7268b9` |
| `801995` | `881521f36ca957c1979cbeed1abe2437afb088f8e957b304ece5061ee6162f73` |

## Canonical 输出与质量

| 输出 | 含义 |
|---|---|
| `data/processed/shenwan/sector_catalog.csv` | 124 条二级目录，含 level、来源和空的 PIT 字段 |
| `data/processed/shenwan/sector_ohlcva.csv` | 419,346 条行业日线，含来源、原始行位置和 `is_valid_ohlc` |
| `data/processed/shenwan/stock_classification_canonical.csv` | 12,920 条历史股票分类，官方/派生区间分列 |
| `data/processed/shenwan/sector_coverage.csv` | 逐行业行数、起止、缺 session 和覆盖率 |
| `data/processed/shenwan/sector_invalid_ohlc.csv` | 20 条异常的完整原值、URL、文件、行号、违规类型与原因分类 |
| `data/processed/shenwan/sector_admission.json` | 准入判定、全部原始 SHA256、全部 canonical SHA256、快照与口径 |

独立重算：124 个行业、419,346 行，1999-12-30 至 2026-09-18；
共同起止 2021-12-13 至 2026-09-18。行业代码唯一、名称覆盖率 100%，
`sector_code + date` 重复 0，volume 和 amount 非空率均为 100%。
volume/amount 的官方单位说明尚未取得，因此只保留源数值，不转换单位。

有 20 条 `SOURCE_INVALID`：原始 JSON 的 `closeindex` 高于 `maxindex`。
19 条发生在 2018-11-06，另 1 条发生在 2014-08-29；并非 parser 更名导致。
保留原值并写入逐条质量 sidecar。loader 在请求范围含异常时默认报错；
仅审计调用可显式 `allow_invalid_for_audit=True`，此开关不会修正数值。

统一 session 日历来自 124 份官方行业观测日期的并集，并通过项目
`TradingCalendar` 表示；不把缺失日期补成行情。全历史各行业自身起止内
缺 session 合计 4,632；共同起止内缺 1,190 个行业-session。
共同区间 1,158 个观测 session 中，822 日全行业齐全、329 日只有 123 行业、
7 日只有 `801952 焦炭Ⅱ`。`801193 证券Ⅱ` 缺 336 个共同区间 session，
是共同覆盖缩短的主要原因。最晚起始行业于 2021-12-13 才有数据；
124 个行业的结束日期均为 2026-09-18。上述缺口未删除，也未填充。

## 分类历史与时点证据

原始 XLS 的唯一 sheet 为 `Sheet1`，四列为股票代码、计入日期、行业代码、
更新日期，共 12,920 行、5,929 个股票代码、553 个行业代码。
`计入日期 → effective_from`，`更新日期 → source_updated_at`。
`effective_to_official`、`available_at`、`classification_version` 均为 null；
来源 URL 中的 `SwClass2021` 和既有脚本的 `SW2021_INDEX` 常量没有当作官方版本证据。
同一股票的下一次计入日期只生成 `effective_to_derived`，共 6,991 条，
状态为 **DERIVED, NOT OFFICIAL**，最后一次记录保持 open ended。

分类 XLS 的 553 个代码与指数目录的 124 个代码直接交集为 0。
两份官方资产使用不同的代码命名空间，不能按代码直接填入
`sector_name/sector_level`，所以分类 canonical 中这两列保持 null。
不能把当前目录名称倒填到历史股票分类，亦不能把下载时间当作历史可得时间。

## 快照、准入与候选区间

`data_snapshot_id`：

```text
872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500
```

指纹输入含分类 XLS、二级目录官方分页及核对副本、124 份历史 raw、行情
manifest 的 SHA256，显式 parser/schema/transform 版本，以及四个转换/准入源码的
SHA256。相同 raw 与代码版本
重跑两次，snapshot ID 和全部五个 canonical 文件 SHA256 均相同。

准入判定为 `FIXED_CLASSIFICATION_RESEARCH`，`strict_pit=false`。
固定的官方二级行业指数目录与历史价格序列已核验；异常已标识且候选区间
不包含这些异常。历史分类版本、官方结束日期、publication/available_at、
指数回算/修订政策与 volume/amount 单位没有充分证据。
**NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST.**

候选研究区间：`2025-04-02` 至 `2026-03-27`。它从共同覆盖中选取连续、
124 行业全部存在且 OHLC 有效的 session，信号起点前保留 120-session 特征预热、
6 个日历月训练窗口与 120-session label/purge 边界，终点后再留 120-session
前瞻标签。区间仅用于数据准备；没有锁定 Development/Validation/OOS，
没有授权 LEVEL B 策略回测。若未来研究允许行业缺日、缩小 universe 或使用
不同历史窗口，须另行批准并重新计算，不能静默改变上述候选范围。

下一阶段可以在此固定分类研究口径下开展 ETF mapping 的数据准备，
但不能宣称严格历史 PIT。升级到 `STRICT_PIT` 需官方分类版本证据、
可审计的有效区间、逐时点 publication timing、无未来分类泄漏证明，
以及行业指数历史回算/修订和成交量/成交额单位说明。

## 运行与测试

仅复用冻结的 `quant-research:py3.12` 容器：

```bash
docker compose exec quant-research python scripts/data/admit_shenwan_sector.py
docker compose exec quant-research python -m pytest -q
docker compose exec quant-research python -m pytest -m 'integration and not network' -q
```

对外读取接口：`src.data.loaders.load_sector_catalog()`、
`load_sector_ohlcva(sector_code, start, end)`、
`load_sector_panel(sector_codes, start, end)`。panel 为有 `date` 和
`sector_code` 的长表；缺 bar 即缺行，无价格填充。loader 核对 canonical
文件 SHA256，默认拒绝请求范围内源头异常行情。
