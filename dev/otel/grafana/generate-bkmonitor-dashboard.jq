def bkmonitor_datasource:
  {
    "type": "bkmonitor-timeseries-datasource",
    "uid": "cfjy28njb6ghsd"
  };

def bkmonitor_promql:
  gsub("\\$\\{agent_code:regex\\}"; "$agent_code")
  | gsub("\\$\\{agent_version:regex\\}"; "$agent_version")
  | gsub("\\$\\{request_model:regex\\}"; "$request_model")
  | gsub("\\$\\{response_model:regex\\}"; "$response_model")
  | gsub("\\$\\{tool_name:regex\\}"; "$tool_name")
  | gsub("\\$\\{handler_type:regex\\}"; "$handler_type")
  | gsub("\\$__range"; "$window")
  | gsub("\\$__rate_interval"; "$window");

def bkmonitor_alias:
  gsub("\\{\\{(?<label>[A-Za-z0-9_]+)\\}\\}"; "$tag_\(.label)");

def bkmonitor_target:
  . as $target
  | {
      "cluster": [],
      "datasource": bkmonitor_datasource,
      "enableDownSampling": true,
      "expressionList": [],
      "format": "time_series",
      "host": [],
      "mode": "code",
      "module": [],
      "promqlAlias": (($target.legendFormat // "") | bkmonitor_alias),
      "query_configs": [],
      "refId": $target.refId,
      "showLastPoint": false,
      "source": ($target.expr | bkmonitor_promql),
      "step": "",
      "type": "range"
    };

def bkmonitor_variable:
  . as $variable
  | $variable
  | .allValue = ".*"
  | .current = {"selected": true, "text": "All", "value": "$__all"}
  | .datasource = bkmonitor_datasource
  | .definition = "- Blueking Monitor - prometheus"
  | .includeAll = true
  | .multi = true
  | .options = []
  | .query = {
      "promql": ($variable.query.query | bkmonitor_promql),
      "queryType": "prometheus"
    }
  | .refresh = 2
  | .regex = ""
  | .skipUrlSync = false
  | .sort = 0;

def window_variable:
  {
    "current": {"text": "1m", "value": "1m"},
    "hide": 0,
    "includeAll": false,
    "multi": false,
    "name": "window",
    "options": [
      {"selected": true, "text": "1m", "value": "1m"},
      {"selected": false, "text": "5m", "value": "5m"},
      {"selected": false, "text": "1h", "value": "1h"}
    ],
    "query": "1m,5m,1h",
    "queryValue": "",
    "skipUrlSync": false,
    "type": "custom"
  };

.
| del(.__inputs)
| .__requires = [
    {
      "type": "datasource",
      "id": "bkmonitor-timeseries-datasource",
      "name": "蓝鲸监控 - 指标数据"
    }
  ]
| .description = "Agent 运行态、耗时、LLM、工具以及应用侧 SSE/Broker 写入压力；数据源为蓝鲸监控指标数据。真实 Broker 积压和磁盘/网络 IO 需要接入 RabbitMQ/Redis 原生 exporter。"
| .editable = true
| .refresh = "1m"
| .tags = ((.tags + ["bkmonitor"]) | unique)
| .time = {"from": "now-1h", "to": "now"}
| .title = "AIDev Agent Metrics (BK Monitor)"
| .uid = "aidev-agent-metrics-bkmonitor"
| .version = 1
| .panels |= map(
    if .type == "row" then
      del(.datasource, .targets)
    else
      .datasource = bkmonitor_datasource
      | .description |= (gsub("\\$__range"; "$window") | gsub("\\$__rate_interval"; "$window"))
      | .targets |= map(bkmonitor_target)
    end
  )
| .templating.list = ((.templating.list | map(bkmonitor_variable)) + [window_variable])
