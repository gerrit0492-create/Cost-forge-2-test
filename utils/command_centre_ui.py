from __future__ import annotations

import streamlit as st

from utils.command_centre_health import CommandCentreHealth, CommandCentreSignal


_STATUS_ICON = {
    'green': '🟢',
    'amber': '🟠',
    'red': '🔴',
}

_SIGNAL_ICON = {
    'ok': '🟢',
    'warning': '🟠',
    'critical': '🔴',
}


def render_health_banner(health: CommandCentreHealth) -> None:
    icon = _STATUS_ICON.get(health.status, '⚪')
    st.markdown(f'### {icon} Project health: {health.score}/100')
    st.progress(health.score / 100)

    if health.status == 'green':
        st.success('Project health is strong. No critical executive signals detected.')
    elif health.status == 'amber':
        st.warning('Project health needs attention. Review the signals below before customer submission.')
    else:
        st.error('Project health is critical. Review issues before approving this estimate.')


def render_signal_list(signals: list[CommandCentreSignal]) -> None:
    for signal in signals:
        icon = _SIGNAL_ICON.get(signal.severity, 'ℹ️')
        with st.container(border=True):
            st.markdown(f'**{icon} {signal.title}**')
            st.caption(signal.message)


def render_health_panel(health: CommandCentreHealth) -> None:
    render_health_banner(health)
    st.markdown('#### Executive signals')
    render_signal_list(health.signals)
