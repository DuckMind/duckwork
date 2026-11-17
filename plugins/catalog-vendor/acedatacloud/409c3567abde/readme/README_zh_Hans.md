# 在Duckwork选择Ace Data Cloud模型：图文指南

[English](../README.md)

安装官方目录中的Ace模型插件后，Duckwork自己的模型/设置列表会显示**Ace Data Cloud**，可直接选gpt-4.1-mini或gpt-4.1，不用手填API地址。它是单独安装的community插件，**不是默认预装**。当前官方第三方产品准入[要求独立插件](https://github.com/DuckMind/duckwork)；旧内置OpenRouter等条目不等于Ace已获默认内置许可。

## 1. 从正式目录安装

打开[Duckwork官方Ace模型页](https://duckwork-agent.fordex.com/docs/plugins/acedatacloud)，核对AceDataCloud维护者。本仓库版本为1.0.2，最低Duckwork0.21.5。官方目录独立固定到审核commit，请以目录显示的版本和SHA为准。

```sh
duckwork plugins install acedatacloud --enable
```

官方安装固定到审核commit；源仓最新README和signup链接改变须经过source release和官方新pin才进入用户安装版本。在需要使用的每个profile分别安装。

## 2. 注册、登录并创建或复制Token

1. 进入[Ace Data Cloud → Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=duckwork_model_zh_readme_api_key)，注册或登录。
2. 打开**General application**，没有时先点**Initialize General Application**。确认聊天模型服务访问权限、[当前价格](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=duckwork_model_zh_readme_pricing)及余额。
3. 复制应用卡片上的**API Key**，或在**Manage Keys → Create**新建`Duckwork models`专用Token，方便单独撤销。
4. 检查有效期、消费限额、Allowed APIs；如限制API，需允许聊天及模型列表接口。通用应用Key按获准服务访问；其他专属服务Key未必有聊天权限。当前图不保证免费额度。
5. 只填Token原文，不带`Bearer `、引号或空格；`platform-...`管理Token不是生成/聊天Key。

![复制API Key或管理Key的真实脱敏Ace控制台截图](https://raw.githubusercontent.com/AceDataCloud/SunoDify/8d3d03570e73324220f111f7fe343da0792a8071/_assets/tutorial/get-api-key-en.png)

![创建专用Token并检查限制的真实控制台截图](https://raw.githubusercontent.com/AceDataCloud/SunoDify/8d3d03570e73324220f111f7fe343da0792a8071/_assets/tutorial/create-api-key-en.png)

图片来自固定SunoDify源提交，已脱敏，2026-10-18核对；图中Dify教程名称为原示例，说明Ace控制台操作，不冒充Duckwork界面。

## 3. 在Duckwork原生选择器填写

```sh
duckwork model
```

选择**Ace Data Cloud**，在凭据输入位置粘贴自己的Key，再选**gpt-4.1-mini**或**gpt-4.1**。不要把Key写进聊天或Git。环境方式可将`ACEDATACLOUD_API_KEY`放入当前profile的secret `.env`，不放非secret `config.yaml`。

插件给出`https://api.acedata.cloud/openai`和`chat_completions`传输，不需要custom-provider YAML。安装后出现原生行不等于无需安装就默认可选。

![官方Duckwork原图编辑预览：Ace模型选择，非实际运行](../assets/tutorial/duckwork-model-picker-preview.png)

此图2026-10-17根据Duckwork官方历史v0.11.0模型选择器截图编辑，原拍摄日未知；**不是实际Ace GUI操作、付费输出或默认预装证据**。[原图出处与边界](../assets/tutorial/SOURCE.md)。真实named provider/key/endpoint/模型列表已在0.21.6/0.22.2合同测试中验证；不冒充当前GUI实拍。

## 4. 首用、结果与媒体任务区别

先核账户当前余额/套餐和这次消费授权。以下命令会发起**收费聊天请求**，教程没有执行该请求，不能直接当预算授权：

```sh
duckwork chat --provider acedatacloud --model gpt-4.1-mini --oneshot "Reply only OK"
```

聊天直接返回文字，不返回媒体task_id。支持上述两模型的文本聊天、流式工具调用和工具结果续轮；模型列表只显示已验证项，不自动替换请求模型。不宣称全catalog、Responses、Messages、vision或可配置reasoning全支持。

若要Suno、Seedance、HappyHorse、GPT Image、Nano Banana，另安装[Ace媒体插件](https://duckwork-agent.fordex.com/docs/plugins/acedatacloud-media)，选择对应toolset并阅读[中英媒体指引](https://github.com/DuckMind/duckwork)。媒体生成只提交一次，保存task_id，pending时只查同ID；模型Provider本身不注册媒体工具，也没有媒体同ID查询接口。

## 5. 常见问题与费用/数据边界

- 没有Ace行：检查已在当前profile安装插件，非其他profile；安装前默认不显示。
- Key无效：检查原文、应用服务访问、聊天和模型列表API权限、有效期/限额/余额；别用媒体专属Key冒充聊天授权。
- 模型缺失：只保留gpt-4.1-mini/gpt-4.1。catalog暂时不可达会显示同一已验证列表，不是自动模型fallback。
- 429限流稍后处理，额度/余额错误先查账单；不把API错误改成成功结果，不发自动替换模型。
- 提示词、工具schema和结果发到公开Ace接口；API Key由Duckwork管理。插件不读别的凭据、不运行shell/后台进程、不自更新或发送遥测。
- 费用以[Ace当前价格](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=duckwork_model_zh_readme_pricing)、你的实际package和权威账单为准；Duckwork估算可能不准确，不用历史截图/测试次数换算营收。

本中文指南随源码版本1.0.2提供。GitHub源码发布与Duckwork目录审核版本分开：按名称安装得到目录当前固定的commit，新文案和带来源参数的native signup链接只在该commit被目录采用后到达用户。升级时先查看目录版本与SHA，再运行`duckwork plugins update acedatacloud`。本文没有发送新的付费请求。
