from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import ItemPedido, Pedido, Produto


@ensure_csrf_cookie
def catalogo(request):
    return render(request, "loja/catalogo.html")


@require_POST
def adicionar_ao_carrinho(request, produto_id):
    if not Produto.objects.filter(pk=produto_id).exists():
        messages.error(request, "Produto não encontrado.")
        return redirect("catalogo")
    carrinho = request.session.get("carrinho", {})
    chave = str(produto_id)
    carrinho[chave] = carrinho.get(chave, 0) + 1
    request.session["carrinho"] = carrinho
    request.session.modified = True
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"itens": sum(carrinho.values())})
    messages.success(request, "Produto adicionado ao carrinho.")
    return redirect("carrinho")


def _montar_carrinho(request):
    carrinho = request.session.get("carrinho", {})
    produtos = Produto.objects.filter(pk__in=[int(key) for key in carrinho])
    itens, total = [], Decimal("0")
    for produto in produtos:
        quantidade = carrinho[str(produto.pk)]
        subtotal = produto.preco * quantidade
        total += subtotal
        itens.append({"produto": produto, "quantidade": quantidade, "subtotal": subtotal})
    return itens, total


def ver_carrinho(request):
    itens, total = _montar_carrinho(request)
    return render(request, "loja/carrinho.html", {"itens": itens, "total": total})


@login_required
def painel_vendedor(request):
    produtos = Produto.objects.filter(vendedor=request.user)
    itens = ItemPedido.objects.filter(
        produto__vendedor=request.user,
        pedido__status__in=("PAGO", "ENVIADO"),
    ).select_related("produto", "pedido")
    vendas_por_categoria = {}
    for item in itens:
        nome_categoria = item.produto.categoria.nome
        vendas_por_categoria[nome_categoria] = vendas_por_categoria.get(nome_categoria, 0) + item.subtotal
    pedidos_recentes = (
        Pedido.objects.filter(itens__produto__vendedor=request.user)
        .select_related("comprador")
        .distinct()
        .order_by("-criado_em")[:5]
    )
    return render(
        request,
        "loja/painel_vendedor.html",
        {
            "produtos": produtos,
            "total_produtos": produtos.count(),
            "estoque_total": sum(produto.estoque for produto in produtos),
            "total_vendido": sum(item.quantidade for item in itens),
            "faturamento": sum(item.subtotal for item in itens),
            "vendas_por_categoria": vendas_por_categoria.items(),
            "pedidos_recentes": pedidos_recentes,
        },
    )


@login_required
@require_POST
def finalizar_compra(request):
    carrinho = request.session.get("carrinho", {})
    if not carrinho:
        messages.warning(request, "Seu carrinho está vazio.")
        return redirect("carrinho")
    try:
        with transaction.atomic():
            produtos = Produto.objects.select_for_update().filter(
                pk__in=[int(key) for key in carrinho]
            )
            por_id = {produto.pk: produto for produto in produtos}
            for chave, quantidade in carrinho.items():
                produto = por_id.get(int(chave))
                if produto is None or produto.estoque < quantidade:
                    nome = produto.nome if produto else f"#{chave}"
                    raise ValueError(f'Estoque insuficiente para "{nome}".')
            pedido = Pedido.objects.create(comprador=request.user)
            for chave, quantidade in carrinho.items():
                produto = por_id[int(chave)]
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=quantidade,
                    preco_unitario=produto.preco,
                )
                Produto.objects.filter(pk=produto.pk).update(
                    estoque=F("estoque") - quantidade
                )
    except ValueError as error:
        messages.error(request, f"{error} Nenhum item foi comprado.")
        return redirect("carrinho")
    request.session["carrinho"] = {}
    messages.success(request, f"Pedido #{pedido.pk} realizado com sucesso!")
    return redirect("catalogo")
