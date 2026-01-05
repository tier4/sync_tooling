import importlib
import json
from typing import TYPE_CHECKING

import jinja2

from diag_master.echarts_adapter import sync_graph_to_echart_options

if TYPE_CHECKING:
    from sync_graph.sync_graph import SyncGraph

ECHART_TEMPLATE = """
<script src="https://cdn.jsdelivr.net/npm/echarts@6.0.0/dist/echarts.min.js"></script>
<div id="sync-doctor-chart" style="width: 100%; aspect-ratio: 16/10;"></div>
<script defer>
    var chart = echarts.init(document.getElementById('sync-doctor-chart'));
    chart.setOption({{echart_options_json}});
</script>
"""


def define_env(env):
    @env.macro
    def label(label: str):
        """Creates an anchor rendering as the given `label` and referenceable through the same label.

        Args:
            label: The text that serves as both the anchor ID and the rendered text. Has to be a
              valid HTML ID.

        Returns:
            The rendered markdown.

        """
        return f"[{label}](#{label}){{ #{label} }}"

    @env.macro
    def ref(label: str):
        """Creates a reference to the anchor with the given `label`. The reference is rendered as
        a link with the given `label` as link text.

        Args:
            label: The label to reference.

        """
        return f"[{label}][{label}]"

    @env.macro
    def visualize_sync_doctor_echart(generator_module_name: str):
        generator = importlib.import_module(generator_module_name)
        if not hasattr(generator, "generate_graph"):
            raise ValueError(
                f"Module '{generator_module_name}' does not have a 'generate_graph' function"
            )

        sg: SyncGraph = generator.generate_graph()  # type: ignore
        echart_options = sync_graph_to_echart_options(sg)
        echart_options["title"]["show"] = False
        echart_options["backgroundColor"] = "transparent"
        echart_options["series"][0]["roam"] = False
        echart_options_json = json.dumps(echart_options)

        template = jinja2.Template(ECHART_TEMPLATE)
        html = template.render(echart_options_json=echart_options_json)
        return html
