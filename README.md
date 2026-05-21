# Kimi Web Folders Plugin

给 `kimi web` 增加**会话文件夹管理**功能，支持把左侧聊天记录收藏到指定文件夹。

## 功能

1. **新建、编辑、删除文件夹**
2. **把会话移动到文件夹**
3. **按文件夹查看会话**

## 安装

```bash
git clone <你的仓库地址>
cd kimi-web-folders-plugin
python3 install.py
```

然后**重启 `kimi web`** 即可生效。

## 使用

启动 `kimi web` 后，打开网页，右下角会出现一个 📁 悬浮按钮，点击进入文件夹管理页面。

## 升级 kimi 后重新安装

`kimi` 升级会覆盖 Python 包里的修改，升级后只需重新执行：

```bash
cd kimi-web-folders-plugin
git pull        # 如果有更新
python3 install.py
```

然后重启 `kimi web`。

## 原理

`install.py` 会自动找到你本地 `kimi-cli` 的安装路径，然后：
- 修改 `session_state.py`、`web/models.py` 等已有文件
- 新增 `web/store/folders.py`、`web/api/folders.py` 等模块
- 新增前端管理页面 `web/static/folders.html`
- 在主页面注入 📁 入口按钮

脚本具有**幂等性**：重复运行是安全的，不会重复修改。

## 数据存储

文件夹数据保存在以下两个位置，升级 `kimi` 不会丢失：

| 数据 | 路径 | 说明 |
|------|------|------|
| 文件夹列表 | `~/.kimi/web_folders.json` | 文件夹名称、ID、排序等信息 |
| 会话所属文件夹 | `~/.kimi/sessions/<id>/state.json` | 每个会话的 `folder_id` 字段 |

卸载插件时数据会保留；如果手动删除 `~/.kimi/web_folders.json`，文件夹列表会清空，但会话文件里的 `folder_id` 仍然保留，重新安装后这些会话会自动回到对应文件夹。

## 兼容性

- 当前基于 `kimi-cli` v1.44.0 开发
- 如果 `kimi-cli` 升级后源码结构发生大变化，`install.py` 会提示无法匹配并退出，此时需要更新本插件

## License

MIT
