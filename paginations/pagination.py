from rest_framework.pagination import PageNumberPagination

# ::: BLOG PAGINATION
class PostPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = "page_size"
    max_page_size = 50

# ::: NOTIFICATION PAGINATION
class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50