from datetime import timedelta

from django.contrib import admin
from django.db.models import F, Sum
from django.utils import timezone

from .models import Avaliacao, Categoria, ItemPedido, Pedido, Produto


def get_dashboard_metrics(request):
    today = timezone.now().date()
    paid_statuses = ["PAGO", "ENVIADO"]

    if not request.user.is_authenticated:
        return {
            "revenue_today": 0,
            "revenue_month": 0,
            "orders_today": 0,
            "orders_month": 0,
            "best_seller": {"name": "N/A", "units": 0, "revenue": 0},
            "best_vendor": {"name": "N/A", "revenue": 0},
            "top_products": [],
            "top_categories": [],
            "daily_series": [],
            "max_daily_revenue": 1,
            "recent_orders": [],
        }

    sales_qs = ItemPedido.objects.filter(pedido__status__in=paid_statuses)
    if not request.user.is_superuser:
        sales_qs = sales_qs.filter(produto__vendedor=request.user)

    revenue_today = sales_qs.filter(pedido__criado_em__date=today).aggregate(
        total=Sum(F("quantidade") * F("preco_unitario"))
    )["total"] or 0
    revenue_month = sales_qs.filter(
        pedido__criado_em__date__gte=today.replace(day=1)
    ).aggregate(total=Sum(F("quantidade") * F("preco_unitario")))['total'] or 0

    orders_qs = Pedido.objects.filter(status__in=paid_statuses)
    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(itens__produto__vendedor=request.user).distinct()

    orders_today = orders_qs.filter(criado_em__date=today).count()
    orders_month = orders_qs.filter(criado_em__date__gte=today.replace(day=1)).count()

    top_products = (
        sales_qs.values("produto__nome")
        .annotate(
            total_unidades=Sum("quantidade"),
            total_receita=Sum(F("quantidade") * F("preco_unitario")),
        )
        .order_by("-total_unidades", "-total_receita")[:5]
    )
    best_seller = top_products[0] if top_products else None

    best_vendor = (
        sales_qs.values(
            "produto__vendedor__username",
            "produto__vendedor__first_name",
            "produto__vendedor__last_name",
        )
        .annotate(total_receita=Sum(F("quantidade") * F("preco_unitario")))
        .order_by("-total_receita")
        .first()
    )

    if best_vendor:
        full_name = " ".join(
            part for part in [best_vendor["produto__vendedor__first_name"], best_vendor["produto__vendedor__last_name"]] if part
        ) or best_vendor["produto__vendedor__username"]
        best_vendor = {"name": full_name, "revenue": best_vendor["total_receita"] or 0}
    else:
        best_vendor = {"name": "N/A", "revenue": 0}

    if best_seller:
        best_seller = {
            "name": best_seller["produto__nome"],
            "units": best_seller["total_unidades"] or 0,
            "revenue": best_seller["total_receita"] or 0,
        }
    else:
        best_seller = {"name": "N/A", "units": 0, "revenue": 0}

    top_categories = (
        sales_qs.values("produto__categoria__nome")
        .annotate(total_receita=Sum(F("quantidade") * F("preco_unitario")))
        .order_by("-total_receita")[:5]
    )

    daily_series = []
    max_daily_revenue = 1
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        order_value = (
            sales_qs.filter(pedido__criado_em__date=day)
            .aggregate(total=Sum(F("quantidade") * F("preco_unitario")))
            ["total"]
            or 0
        )
        if order_value > max_daily_revenue:
            max_daily_revenue = order_value
        daily_series.append(
            {
                "label": day.strftime("%d/%m"),
                "revenue": order_value,
                "orders": orders_qs.filter(criado_em__date=day).count(),
            }
        )

    recent_orders = Pedido.objects.filter(status__in=paid_statuses)
    if not request.user.is_superuser:
        recent_orders = recent_orders.filter(itens__produto__vendedor=request.user).distinct()
    recent_orders = (
        recent_orders.select_related("comprador")
        .prefetch_related("itens__produto")
        .order_by("-criado_em")[:5]
    )

    recent_orders_list = []
    for pedido in recent_orders:
        recent_orders_list.append(
            {
                "id": pedido.pk,
                "comprador": pedido.comprador.get_full_name() or pedido.comprador.username,
                "data": pedido.criado_em.strftime("%d/%m/%Y"),
                "total": pedido.total,
                "status": pedido.get_status_display(),
            }
        )

    return {
        "revenue_today": revenue_today,
        "revenue_month": revenue_month,
        "orders_today": orders_today,
        "orders_month": orders_month,
        "best_seller": best_seller,
        "best_vendor": best_vendor,
        "top_products": list(top_products),
        "top_categories": list(top_categories),
        "daily_series": daily_series,
        "max_daily_revenue": max_daily_revenue,
        "recent_orders": recent_orders_list,
    }


def dashboard_each_context(request):
    context = admin.site.__class__.each_context(admin.site, request)
    context["dashboard_metrics"] = get_dashboard_metrics(request)
    return context


admin.site.index_template = "admin/dashboard_index.html"
admin.site.each_context = dashboard_each_context


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "preco", "estoque", "vendedor")
    list_filter = ("categoria",)
    search_fields = ("nome", "descricao")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.filter(vendedor=request.user)

    def get_exclude(self, request, obj=None):
        return None if request.user.is_superuser else ("vendedor",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.vendedor_id:
            obj.vendedor = request.user
        super().save_model(request, obj, form, change)


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ("preco_unitario",)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "comprador", "status", "criado_em")
    list_filter = ("status",)
    inlines = [ItemPedidoInline]


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("produto", "usuario", "nota", "criada_em")
    list_filter = ("nota",)
    search_fields = ("produto__nome", "usuario__username", "comentario")
    readonly_fields = ("produto", "usuario", "criada_em")
