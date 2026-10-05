# ফাইল: backend/utils/pagination.py
# এই ফাইলটি API response-এ pagination নিয়ন্ত্রণের জন্য custom pagination classes ধারণ করে।

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination - প্রতি পেজে ২০টি রেকর্ড।
    Frontend থেকে ?page=2&page_size=50 দিয়ে control করা যাবে।
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,     # মোট রেকর্ড সংখ্যা
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


class LargeResultsSetPagination(PageNumberPagination):
    """বড় dataset-এর জন্য pagination - প্রতি পেজে ৫০টি রেকর্ড।"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })
