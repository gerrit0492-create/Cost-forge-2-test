class APIService:

    @staticmethod
    def build_project_payload(project_name, customer, total_cost):

        return {
            'project_name': project_name,
            'customer': customer,
            'total_cost': total_cost,
        }
