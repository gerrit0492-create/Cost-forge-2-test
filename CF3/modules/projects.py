import streamlit as st

from CF3.services.database_service import DatabaseService



def render():
    st.title('Projects')
    st.caption('Enterprise project management')

    db = DatabaseService()
    db.initialize()

    with st.form('new_project'):
        project_name = st.text_input('Project Name')
        customer = st.text_input('Customer')

        submitted = st.form_submit_button('Create Project')

        if submitted and project_name:
            conn = db.connect()
            cursor = conn.cursor()

            cursor.execute(
                'INSERT INTO projects (name, customer) VALUES (?, ?)',
                (project_name, customer),
            )

            conn.commit()
            conn.close()

            st.success(f'Project created: {project_name}')
