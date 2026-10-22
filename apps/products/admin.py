from django.contrib import admin

from apps.products.models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "category", "price", "discount_price", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["name", "sku"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]
    # select_related để trang list Admin không bị N+1 khi hiển thị category
    list_select_related = ["category"]
