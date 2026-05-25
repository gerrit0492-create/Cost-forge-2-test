import pandas as pd


class BOMHierarchyEngine:

    @staticmethod
    def build_parent_child_structure(df):

        required = [
            'Part Number',
            'Parent Part',
            'Description',
            'Qty'
        ]

        for col in required:
            if col not in df.columns:
                raise ValueError(f'Missing required column: {col}')

        hierarchy = {}

        for _, row in df.iterrows():

            parent = row['Parent Part']

            item = {
                'part_number': row['Part Number'],
                'description': row['Description'],
                'qty': row['Qty'],
            }

            if parent not in hierarchy:
                hierarchy[parent] = []

            hierarchy[parent].append(item)

        return hierarchy

    @staticmethod
    def detect_orphans(df):

        parts = set(df['Part Number'])
        parents = set(df['Parent Part'])

        orphans = parents - parts

        return list(orphans)

    @staticmethod
    def summarize_levels(df):

        if 'Level' not in df.columns:
            return pd.DataFrame()

        summary = (
            df.groupby('Level')
            .size()
            .reset_index(name='Part Count')
        )

        return summary
