# 专业网址知识库

当用户进行模糊搜索（"搜一下XXX"）时，根据查询关键词在本知识库中匹配对应的专业/权威网址，使用 curl 直接抓取内容。与搜索引擎结果并行获取，合并回答。

---

## 匹配策略

1. 扫描用户查询中的关键词，在下方各分类中查找匹配条目
2. 找到匹配后，选取 1~3 个最相关的 URL（优先 🀄 中文站点）
3. 用 curl 直接抓取：`curl -s -L "{URL}"`
4. 只有从头到尾完整扫描本文件后，才能判定知识库无匹配；无匹配时进入 [authoritative-url-discovery.md](authoritative-url-discovery.md) 动态发现权威网址，动态发现仍无合格结果时才仅使用搜索引擎结果

---

## 💻 计算机/编程

### React
- 关键词: react, hooks, jsx, redux, next.js, nextjs, umi, antd, zustand
- 🀄 https://zh-hans.react.dev (React 官方中文文档)
- https://react.dev (React 官方英文文档)

### Vue
- 关键词: vue, vue3, pinia, vite, nuxt, nuxt3, element plus
- https://vuejs.org (Vue 官方英文)

### Angular
- 关键词: angular, rxjs, ngrx
- https://angular.dev (Angular 官方英文)

### Svelte
- 关键词: svelte, sveltekit
- https://svelte.dev (Svelte 官方文档)
- 🀄 https://svelte.cn (Svelte 中文社区)

### TypeScript
- 关键词: typescript, ts, type, interface, enum
- 🀄 https://ts.nodejs.cn (TypeScript 中文手册)
- https://www.typescriptlang.org (TypeScript 官方)

### JavaScript / MDN
- 关键词: javascript, js, es6, es2023, web api, dom, css, html, fetch, canvas
- 🀄 https://developer.mozilla.org/zh-CN (MDN Web 文档中文)
- https://developer.mozilla.org (MDN Web 文档英文)

### Node.js
- 关键词: node, nodejs, npm, express, koa, fastify, nestjs
- 🀄 https://nodejs.cn (Node.js 中文网)
- https://nodejs.org (Node.js 官方)

### Python
- 关键词: python, pip, conda, pandas, numpy, scipy
- 🀄 https://docs.python.org/zh-cn/3 (Python 官方中文文档)
- https://docs.python.org/3 (Python 官方英文文档)
- https://pypi.org (PyPI 包索引)

### Go
- 关键词: go, golang, gin, echo, gorm
- https://go.dev (Go 官方文档)

### Rust
- 关键词: rust, cargo, tokio, actix, serde
- 🀄 https://rustwiki.org (Rust 中文社区文档)
- https://doc.rust-lang.org (Rust 官方文档)
### Java / JVM
- 关键词: java, jvm, maven, gradle, spring, springboot, mybatis, hibernate
- 🀄 https://springdoc.cn (Spring 中文文档)
- https://docs.oracle.com/en/java (Java 官方文档)
- https://central.sonatype.com (Maven Central)

### C / C++
- 关键词: c++, cpp, cmake, qt, boost, stl
- https://en.cppreference.com (C/C++ 参考手册)

### C# / .NET
- 关键词: c#, dotnet, .net, asp.net, blazor, xamarin
- 🀄 https://learn.microsoft.com/zh-cn/dotnet (.NET 中文文档)
- https://learn.microsoft.com/en-us/dotnet (.NET 官方文档)

### PHP
- 关键词: php, laravel, symfony, wordpress, composer
- https://laravel.com (Laravel 官方文档)

### Ruby
- 关键词: ruby, rails, gem, rspec
- 🀄 https://ruby-china.org (Ruby China 社区)
- https://rubygems.org (RubyGems)

### Kotlin
- 关键词: kotlin, ktor, coroutine
- 🀄 https://book.kotlincn.net (Kotlin 中文文档)
- https://kotlinlang.org (Kotlin 官方)

### Swift / iOS
- 关键词: swift, ios, xcode, swiftui, uikit
- 🀄 https://swiftgg.gitbook.io (Swift 中文翻译)

### Tailwind CSS
- 关键词: tailwind, tailwindcss, utility css
- 🀄 https://tailwind.nodejs.cn (Tailwind CSS 中文文档)
- https://tailwindcss.com (Tailwind CSS 官方)

### Ant Design
- 关键词: antd, ant design, antdesign
- 🀄 https://ant-design.antgroup.com (Ant Design 中文)
- https://ant.design (Ant Design)

### ECharts
- 关键词: echarts, chart, 图表, 数据可视化
- 🀄 https://echarts.apache.org/zh (ECharts 中文)
- https://echarts.apache.org (ECharts 官方)

### Kubernetes
- 关键词: kubernetes, k8s, helm, istio, pod
- 🀄 https://kubernetes.io/zh-cn (Kubernetes 中文文档)
- https://kubernetes.io (Kubernetes 官方)

### Nginx
- 关键词: nginx, 反向代理, reverse proxy, load balance
- https://nginx.org (Nginx 官方文档)

### Git / GitHub
- 关键词: git, github, gitlab, gitee, 版本控制
- https://git-scm.com (Git 官方文档)

### Linux
- 关键词: linux, ubuntu, debian, centos, arch, command, bash, shell, systemd
- 🀄 https://manpages.debian.org (Debian 手册页)
- https://www.kernel.org (Linux 内核)
- https://wiki.archlinux.org (Arch Wiki — 最佳 Linux 参考)

### PostgreSQL
- 关键词: postgresql, postgres, pg
- https://www.postgresql.org (PostgreSQL 官方文档)

### MongoDB
- 关键词: mongodb, mongo, nosql, mongoose
- https://www.mongodb.com/docs (MongoDB 官方文档)

### Redis
- 关键词: redis, 缓存, cache, 消息队列
- https://redis.io (Redis 官方文档)

## 🤖 AI / 机器学习

### PyTorch
- 关键词: pytorch, torch, tensor, cuda, gpu training
- https://pytorch.org (PyTorch 官方文档)

### Hugging Face
- 关键词: huggingface, transformers, nlp, llm, model, bert, gpt
- 🀄 https://hf-mirror.com (Hugging Face 国内镜像)

### OpenAI
- 关键词: openai, chatgpt, gpt-4, gpt-4o, dall-e, whisper, tts
- https://openai.com (OpenAI 官网)

### Ollama
- 关键词: ollama, llama, local llm, 本地模型, deepseek
- https://ollama.com (Ollama 官方)

## 🎓 学术/教育

### 中国知网 (CNKI)
- 关键词: 知网, cnki, 论文, 期刊, 硕博论文, 学术
- 🀄 https://www.cnki.net (中国知网)

### arXiv
- 关键词: arxiv, 预印本, preprint, physics, math, cs
- https://arxiv.org (arXiv 预印本)

### PubMed
- 关键词: pubmed, 医学论文, 生物医学, clinical trial
- https://pubmed.ncbi.nlm.nih.gov (PubMed 生物医学文献)

### 考研
- 关键词: 考研, 研究生, 调剂, 国家线, 复试
- 🀄 https://yz.chsi.com.cn (中国研究生招生信息网)

### 留学
- 关键词: 留学, 雅思, 托福, gre, gmat, 出国, study abroad
- https://www.ets.org/toefl (托福官方)

### 中国大学MOOC
- 关键词: mooc, 网课, 公开课, 慕课, coursera
- 🀄 https://www.icourse163.org (中国大学MOOC)
- https://www.coursera.org (Coursera)

### 英语学习
- 关键词: 英语, 单词, 语法, 听力, english
- 🀄 https://dict.youdao.com (有道词典)
- https://dictionary.cambridge.org (剑桥词典)

---

## 💰 金融/投资

### 东方财富
- 关键词: a股, 股票, 行情, 财报, 分红, 北向资金
- 🀄 https://www.eastmoney.com (东方财富)

### 同花顺
- 关键词: 同花顺, 炒股, 技术分析, k线
- 🀄 https://www.10jqka.com.cn (同花顺)

### 中国人民银行
- 关键词: 央行, 利率, 存款准备金, 货币政策, LPR
- 🀄 https://www.pbc.gov.cn (中国人民银行)

### 证监会
- 关键词: 证监会, ipo, 注册制, 信息披露
- 🀄 https://www.csrc.gov.cn (中国证监会)

### 上海证券交易所
- 关键词: 上交所, 科创板, 股票上市
- 🀄 https://www.sse.com.cn (上海证券交易所)

### 深圳证券交易所
- 关键词: 深交所, 创业板
- 🀄 https://www.szse.cn (深圳证券交易所)

### 基金
- 关键词: 基金, etf, lof, 定投, 基金经理
- 🀄 https://www.chinaamc.com (华夏基金)
- 🀄 https://fund.eastmoney.com (天天基金)

### 保险
- 关键词: 保险, 重疾险, 医疗险, 车险, 寿险
- 🀄 https://www.iachina.cn (中国保险行业协会)

### 集思录
- 关键词: 可转债, 分级基金, 套利, 低风险投资
- 🀄 https://www.jisilu.cn (集思录)

---

## ⚖️ 法律/政策

### 北大法宝
- 关键词: 法律, 法规, 判决, 案例, 司法解释, 合同
- 🀄 https://www.pkulaw.com (北大法宝 — 法律法规检索系统)

---

## 🏥 医疗/健康

### 默沙东诊疗手册
- 关键词: 疾病, 症状, 诊断, 治疗, 用药
- 🀄 https://www.msdmanuals.cn (默沙东诊疗手册 — 中文专业版)
- 🀄 https://www.msdmanuals.cn/home (默沙东诊疗手册 — 中文家庭版)

### 丁香园
- 关键词: 丁香园, 医生, 临床, 指南, 医学
- 🀄 https://www.dxy.cn (丁香园)

### 丁香医生
- 关键词: 丁香医生, 健康科普, 症状自查, 就医
- 🀄 https://dxy.com (丁香医生)

### WHO (世界卫生组织)
- 关键词: who, 世卫, 疫情, 传染病, 疫苗
- 🀄 https://www.who.int/zh (WHO 中文)
- https://www.who.int (WHO 英文)

### 中国疾控中心
- 关键词: cdc, 疾控, 传染病, 疫苗接种
- 🀄 https://www.chinacdc.cn (中国疾病预防控制中心)

## ✈️ 旅游/出行

### 携程旅行
- 关键词: 携程, 酒店, 机票, 火车票, 景点门票
- 🀄 https://www.ctrip.com (携程)

### 12306
- 关键词: 12306, 高铁, 火车票, 动车
- 🀄 https://www.12306.cn (铁路12306)

### 各航司官网
- 关键词: 航班, 飞机, 登机, 行李, 航空公司
- 🀄 https://www.csair.com/cn (南航)

---

## 🍔 美食/餐饮

### 下厨房
- 关键词: 菜谱, 做饭, 烘焙, 家常菜, 食谱
- 🀄 https://www.xiachufang.com (下厨房)

### 食品安全
- 关键词: 食品安全, 添加剂, 保质期, 农药残留, 转基因
- 🀄 https://www.cfsa.net.cn (国家食品安全风险评估中心)
- 🀄 https://www.samr.gov.cn (国家市场监督管理总局)

---

## 🚗 汽车/交通

### 汽车之家
- 关键词: 汽车, 车型, 报价, 评测, suv, 轿车
- 🀄 https://www.autohome.com.cn (汽车之家)

### 易车
- 关键词: 易车, 购车, 比价, 经销商
- 🀄 https://www.yiche.com (易车)

### 新能源汽车
- 关键词: 新能源, 电动车, 充电桩, 比亚迪, 特斯拉, 蔚来
- 🀄 https://www.autohome.com.cn (汽车之家新能源频道)

### 汽车评测（海外）
- 关键词: car review, 汽车评测, 碰撞测试, iihs, ncap
- https://www.iihs.org (IIHS 碰撞测试)
- https://www.euroncap.com (Euro NCAP)

---

## 🏠 房产/家居

### 住房和城乡建设部
- 关键词: 住建部, 房地产政策, 限购, 公积金
- 🀄 https://www.mohurd.gov.cn (住建部)

## ⚽ 体育/健身

### 虎扑
- 关键词: 篮球, nba, cba, 足球, 中超, 英超, 西甲
- 🀄 https://www.hupu.com (虎扑体育)

### 腾讯体育
- 关键词: 腾讯体育, 直播, 赛事, 比分
- 🀄 https://sports.qq.com (腾讯体育)

### 懂球帝
- 关键词: 足球, 欧冠, 世界杯, 五大联赛
- 🀄 https://www.dongqiudi.com (懂球帝)

### 国家体育总局
- 关键词: 体育总局, 竞技体育, 全民健身
- 🀄 https://www.sport.gov.cn (国家体育总局)

### Keep
- 关键词: keep, 健身, 减脂, 增肌, hiit, 跑步
- 🀄 https://www.keep.com (Keep)

## 🎬 娱乐/影视

### 豆瓣电影
- 关键词: 电影, 影评, 评分, 电视剧, 综艺
- 🀄 https://movie.douban.com (豆瓣电影)

### 烂番茄 (Rotten Tomatoes)
- 关键词: rotten tomatoes, 烂番茄, tomatometer
- https://www.rottentomatoes.com (Rotten Tomatoes)

### B站
- 关键词: bilibili, b站, 番剧, up主, 弹幕
- 🀄 https://www.bilibili.com (B站)

### QQ音乐
- 关键词: qq音乐, 歌曲, 演唱会
- 🀄 https://y.qq.com (QQ音乐)

### 综艺/电视剧
- 关键词: 综艺, 网剧, 电视剧, 追剧
- 🀄 https://movie.douban.com (豆瓣 — 电视剧频道)

---

## 🛒 购物/消费

### 数字尾巴 / 爱范儿（数码评测）
- 关键词: 数码, 评测, 手机, 电脑, 耳机
- 🀄 https://www.ifanr.com (爱范儿)

## 👶 教育/亲子

### 中国教育部
- 关键词: 教育部, 高考, 中考, 双减, 学区
- 🀄 https://www.moe.gov.cn (中国教育部)

### 宝宝树
- 关键词: 怀孕, 育儿, 月子, 辅食, 早产
- 🀄 https://www.babytree.com (宝宝树)

### 亲宝宝
- 关键词: 新生儿, 黄疸, 疫苗, 发育, 儿保
- 🀄 https://www.qinbaobao.com (亲宝宝)

### 学而思 / 新东方
- 关键词: 学而思, 新东方, 补习, 奥数, 英语培训
- 🀄 https://www.xdf.cn (新东方)

---

## 📚 百科/知识

### 国家统计局
- 关键词: gdp, cpi, 人口, 统计, 数据
- 🀄 https://www.stats.gov.cn (国家统计局)

### 世界银行数据
- 关键词: world bank, gdp per capita, 各国数据
- https://data.worldbank.org (World Bank Open Data)

---

## 🌐 新闻/资讯

### 新华社/人民网
- 关键词: 新华社, 新闻, 人民日报, 官方媒体
- 🀄 https://www.people.com.cn (人民网)

### 财新网
- 关键词: 财新, 经济新闻, 深度报道
- 🀄 https://www.caixin.com (财新)

## 💼 办公/效率工具

### WPS / Office
- 关键词: wps, word, excel, ppt, 办公, 文档, 表格
- 🀄 https://support.microsoft.com/zh-cn (Microsoft 中文支持)

### 钉钉 (DingTalk)
- 关键词: 钉钉, 考勤, 打卡, 视频会议, 审批流
- 🀄 https://www.dingtalk.com (钉钉官网)

### 企业微信
- 关键词: 企业微信, 客户群, 离职继承, 私域
- 🀄 https://work.weixin.qq.com (企业微信)

### 项目管理
- 关键词: 项目管理, 甘特图, 看板, 敏捷, scrum
- 🀄 https://www.teambition.com (Teambition)
- 🀄 https://www.tapd.cn (TAPD 腾讯敏捷协作)

### 会议/视频会议
- 关键词: zoom, teams, 腾讯会议, 视频会议
- 🀄 https://meeting.tencent.com (腾讯会议)
- https://zoom.us (Zoom)

### 日历/日程
- 关键词: 日历, 日程, 时间管理, gtd
- https://calendly.com (Calendly 预约)
- 🀄 https://ticktick.com (滴答清单)

### 简历/求职
- 关键词: 简历, 求职, 面试, 招聘, 薪资
- 🀄 https://www.liepin.com (猎聘)

---

## 📊 市场调研/行业报告

### 艾瑞咨询
- 关键词: 艾瑞, 行业报告, 用户研究, 市场规模
- 🀄 https://www.iresearch.cn (艾瑞咨询)

### 易观分析
- 关键词: 易观, 数字用户, 行业分析
- 🀄 https://www.analysys.cn (易观分析)

### QuestMobile
- 关键词: questmobile, app数据, 用户画像, 流量
- 🀄 https://www.questmobile.com.cn (QuestMobile)

### 199IT
- 关键词: 199it, 数据报告, 互联网数据
- 🀄 https://www.199it.com (199IT 数据报告)

### TalkingData
- 关键词: talkingdata, 移动数据, 用户行为
- 🀄 https://www.talkingdata.com (TalkingData)

### 巨潮资讯
- 关键词: 年报, 招股书, 上市公司公告
- 🀄 https://www.cninfo.com.cn (巨潮资讯 — 证监会指定信息披露)

## 📈 数据分析

### 数据查询/公共数据
- 关键词: 开放数据, 公共数据, 数据集
- https://data.worldbank.org (World Bank Open Data)

---

## 📱 自媒体运营/内容创作

### 新榜
- 关键词: 新榜, 自媒体排行, 内容数据, 达人
- 🀄 https://www.newrank.cn (新榜)

### Canva
- 关键词: canva, 设计, 封面, 海报, 模版, 作图
- 🀄 https://www.canva.cn (Canva 中文)
- https://www.canva.com (Canva)

### 版权/素材
- 关键词: 无版权, 图片, 字体, 音乐, 视频素材
- https://pixabay.com (Pixabay 免费素材)

---

## 🔥 热点/热搜

### 百度热搜
- 关键词: 百度热搜, 实时热点, 搜索风云榜
- 🀄 https://top.baidu.com (百度热搜)

### 微信指数
- 关键词: 微信指数, 热度趋势, 朋友圈热度
- 🀄 https://weixin.qq.com (微信内搜索"微信指数"小程序)

## 🎨 潮流/时尚

### NOWRE
- 关键词: nowre, 潮流, 街头, 滑板
- 🀄 https://www.nowre.com (NOWRE)

### 色采/配色
- 关键词: 配色, 色板, 颜色搭配, 潘通
- https://coolors.co (Coolors)

## 使用说明

1. **按需爬取**：匹配到条目后，选取 1~3 个 URL 用 curl 直接抓取
2. **优先中文**：标记 🀄 的为中文站点，优先使用
3. **并行爬取**：多个 URL 可并行 curl，节省时间
4. **未匹配处理**：必须完整扫描本文件后再判定未匹配；未匹配时进入动态权威网址发现，动态发现仍无合格结果时才仅用搜索引擎结果回答
5. **可扩展**：该知识库为 Markdown 文件，随时添加新条目
