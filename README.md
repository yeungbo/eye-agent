# 眼健康自查助手 · Linux 部署包
> **作者**：杨博 (yangbo621@163.com)　·　**许可**：Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)（[https://creativecommons.org/licenses/by-nc/4.0/](https://creativecommons.org/licenses/by-nc/4.0/)）
> 仅供学习与非商业用途；商业使用须另行获得作者书面授权。详见 `LICENSE.txt` / `NOTICE.md`。

一套**离线、自包含**的中医眼科辨证辅助服务：11 题采集 → 本地知识库检索 → 五轮/脏腑辨证 → 生成带逐条出处（含《黄帝内经》《银海精微》《原机启微》《审视瑶函》等古籍原文）的报告，并按手机号归档。

全程**不联网、不上传任何数据**，知识库与依赖均随包携带。

---

## 一、环境要求

| 项目 | 要求 |
|---|---|
| 系统 | Ubuntu 20.04 / 22.04 / 24.04，Debian 11+（其它 systemd 发行版亦可） |
| 架构 | x86_64（arm64 需联网安装依赖） |
| Python | ≥ 3.9（系统自带即可，脚本会自建独立虚拟环境） |
| 内存 | ≥ 512 MB |
| 磁盘 | ≥ 500 MB |
| 权限 | root（sudo） |

> 依赖安装默认使用包内 `wheels/` 离线安装，已内置 **CPython 3.10 与 3.12** 两套 wheel，覆盖 Ubuntu 22.04 / 24.04 两大 LTS，装完即用、全程不联网。
> 若目标机是其它 Python 版本（如 3.11），改用联网安装：`sudo bash install.sh --online`。

---

## 二、安装

```bash
tar -xzf eye-agent-<版本>-linux-x86_64.tar.gz
cd eye-agent-<版本>
sudo bash install.sh
```

常用参数：

```bash
sudo bash install.sh --port 8080          # 换端口（默认 8765）
sudo bash install.sh --host 127.0.0.1     # 只本机访问（默认 0.0.0.0，局域网可访问）
sudo bash install.sh --dir /data/eye      # 换安装目录（默认 /opt/eye-agent）
sudo bash install.sh --online             # 联网安装依赖（忽略内置 wheel）
sudo bash install.sh --no-systemd         # 不注册 systemd（容器 / WSL 场景）
```

安装完成后会打印访问地址：

```
本机访问：  http://127.0.0.1:8765
局域网访问：http://192.168.x.x:8765
```

浏览器打开即可使用。

---

## 三、日常管理

```bash
eye-agent start|stop|restart|status   # 服务控制
eye-agent enable|disable              # 开机自启开关
eye-agent logs [行数]                  # 跟踪错误日志
eye-agent url                          # 打印访问地址
eye-agent env                          # 查看当前配置
eye-agent health                       # 健康检查
```

等价的 systemctl 写法同样可用：`systemctl restart eye-agent`。

### 无 systemd 的环境（Docker 容器 / WSL / 部分 VPS）

若安装时未检测到 systemd，安装脚本会自动改为**后台进程模式**，管理命令完全相同（内部用 `pgrep`/`kill` 管理，不调用 systemctl）：

```bash
sudo eye-agent start      # 拉起后台进程
sudo eye-agent stop       # 停止
sudo eye-agent status     # 查看 PID 与访问地址
sudo eye-agent enable     # 写入 crontab @reboot 实现开机自启
```

也可直接前台运行排查问题（会打印完整报错）：

```bash
sudo /opt/eye-agent/start.sh
```

**修改端口 / 监听地址**：编辑 `/etc/eye-agent.env`，然后 `sudo systemctl restart eye-agent`。

---

## 四、安装位置

| 用途 | 路径 |
|---|---|
| 程序 | `/opt/eye-agent/app`（后端 + 前端页面） |
| 知识库 | `/opt/eye-agent/references`（11 个专科文件，约 1.2 MB） |
| 虚拟环境 | `/opt/eye-agent/venv` |
| **档案数据** | `/var/lib/eye-agent/data`（`records.json` 索引 + `results/` 完整结果） |
| **报告文件** | `/var/lib/eye-agent/reports`（Markdown + HTML） |
| 日志 | `/var/log/eye-agent/{access,error}.log` |
| 配置 | `/etc/eye-agent.env` |
| 服务 | `/etc/systemd/system/eye-agent.service` |

> 数据目录与程序目录分离，**重新执行 install.sh 覆盖安装不会丢失历史档案与报告**。

---

## 五、卸载

```bash
sudo bash uninstall.sh            # 卸载程序，保留档案与报告
sudo bash uninstall.sh --purge    # 连数据一起删除（不可恢复）
```

---

## 六、使用说明

1. 打开页面，输入 11 位手机号建档（**仅本机保存**，列表展示一律脱敏为 `138****8888`）
2. 依次回答 11 题（年龄区间、主症、病程、眼别、视力变化、伴随症状、全身症状、舌象、诱因、既往史、外伤/化学伤）
3. 提交后得到报告：病种方向（含西医对应）、五轮定位、证型、治法方药、涉药安全四关、日常调护、古籍经典佐证
4. 每条结论下点「查看依据 / 参考资料」可展开逐条出处，经典原文以 📜 标注
5. 报告可下载 Markdown / HTML
6. 首页「查历史报告」输入同一手机号即可调阅历次记录

---

## 七、多人同时使用

**支持多人同时访问**，彼此数据互不可见。

- **并发能力**：服务为异步单进程 + 工作线程池，实测 30 人同时提交全部成功（约 3.8 秒完成一轮）；日常十几人同时使用无压力。检索在本地内存索引中完成，不联网、无外部依赖。
- **报告不会串号**：每次咨询的报告文件名含「时间戳 + 手机号尾号」，并在内核层面用独占创建（`O_EXCL`）分配，同秒提交也会自动递增序号。修复前曾存在同秒撞名导致后来者覆盖（甚至写坏）前人报告的问题。
- **写入原子化**：报告与档案均先写临时文件再原子替换，任何时刻都不会读到写了一半的内容。
- **访问隔离**：历史报告按手机号精确过滤；调阅与下载均校验归属，用他人手机号访问他人报告一律返回 404。
- **隐私**：索引与页面展示一律脱敏（`138****8888`），完整手机号仅用于精确匹配，不下发给列表接口；数据全部留在 `/var/lib/eye-agent`，不上传。

> 若部署给较多人使用（数十人并发），可在 `/etc/eye-agent.env` 中调整端口，必要时用多实例 + 反向代理横向扩展。

---

## 八、常见问题

**Q：局域网其它电脑打不开？**
A：确认安装时用的是默认 `0.0.0.0`；若启用了 ufw，执行 `sudo ufw allow 8765/tcp`。

**Q：端口被占用？**
A：`sudo bash install.sh --port 8080` 重装，或改 `/etc/eye-agent.env` 后 `sudo systemctl restart eye-agent`。

**Q：服务起不来？**
A：`eye-agent logs` 或 `tail -n 50 /var/log/eye-agent/error.log`；多数为端口占用或 Python 版本过低。

**Q：离线装不上依赖？**
A：包内 wheel 覆盖 CPython 3.10 / 3.12。其它版本请用 `sudo bash install.sh --online`；完全内网环境可在同版本联网机上 `pip download -r requirements.txt -d wheels --platform manylinux2014_x86_64 --python-version <版本> --only-binary=:all:`，把 `wheels/` 放回安装包目录再装。

**Q：`nohup: failed to run command '/opt/eye-agent/venv/bin/python': Permission denied`？**
A：1.0.1 已修复（安装脚本会把整棵安装树权限归一为目录 755 / 文件 644）。若仍出现，手工执行：
`sudo find /opt/eye-agent -type d -exec chmod 755 {} + && sudo find /opt/eye-agent -type f -not -path "*/venv/bin/*" -exec chmod 644 {} +`，然后 `sudo eye-agent restart`。

**Q：`systemctl: command not found`？**
A：当前环境没有 systemd（容器 / WSL）。用 1.0.1 重新安装即可自动切换到进程模式；管理命令照常使用 `eye-agent start|stop|restart|status`。

**Q：数据怎么备份？**
A：打包 `/var/lib/eye-agent` 整个目录即可（档案 + 全部报告都在里面）。

---

## 九、接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/questions` | 获取 11 题问卷 |
| POST | `/api/consult` | 提交 `{phone, answers}`，返回辨证结果与报告 |
| GET | `/api/reports?phone=` | 按手机号查历史报告（脱敏） |
| GET | `/api/records/<id>?phone=` | 调阅单次完整结果（校验归属） |
| GET | `/api/health` | 健康检查与知识库统计 |
| GET | `/reports/<文件名>?phone=` | 下载报告（须带建档手机号校验归属） |

---

## ⚠ 免责声明

本工具为中医眼科**学习参考**工具，**不构成医疗诊断**，也不能替代执业医师面诊与眼科专科检查（视力、眼压、裂隙灯、眼底/OCT）。

出现以下情况请**立即就医**，不要依赖本工具：

- 视力突然下降或丧失
- 眼胀痛伴头痛、恶心呕吐、看灯有彩虹圈
- 眼球穿通伤、酸碱化学伤
- 小儿瞳孔区发白

具体用药须经执业中医师 / 中医眼科医师处方。

---

## 📄 版权与许可

- **作者**：杨博（yangbo621@163.com）
- **许可**：Attribution-NonCommercial 4.0 International（CC BY-NC 4.0）
- **许可全文**：`LICENSE.txt`（官方页面 https://creativecommons.org/licenses/by-nc/4.0/）
- **署名与第三方声明**：`NOTICE.md`

你可以自由**共享与改编**本项目，但必须**保留作者署名**，且**不得用于商业目的**；
商业使用须事先取得作者书面授权。每个源码文件头部均已标注 `@author` 与 `@license`，请勿删除。

依赖的第三方组件（Python / FastAPI / Uvicorn / Pydantic 等）沿用其自身许可，详见 `NOTICE.md`。
