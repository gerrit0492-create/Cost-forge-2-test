import logging

import streamlit as st

logger = logging.getLogger(__name__)


def guard(fn):
    try:
        fn()
    except Exception as e:
        logger.exception("Unhandled error in guarded function")
        st.error(f"{type(e).__name__}: {e}")
        st.stop()
