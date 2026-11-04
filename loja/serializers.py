from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from .models import ItemPedido, Pedido, Produto


class ProdutoSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.CharField(source="categoria.nome", read_only=True)

    class Meta:
        model = Produto
        fields = [
            "id", "nome", "descricao", "preco", "estoque", "categoria",
            "categoria_nome", "vendedor",
        ]
        read_only_fields = ["vendedor"]


class ItemPedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPedido
        fields = ["produto", "quantidade", "preco_unitario"]
        read_only_fields = ["preco_unitario"]


class PedidoSerializer(serializers.ModelSerializer):
    itens = ItemPedidoSerializer(many=True)

    class Meta:
        model = Pedido
        fields = ["id", "status", "criado_em", "itens"]
        read_only_fields = ["status", "criado_em"]

    def validate_itens(self, itens):
        if not itens:
            raise serializers.ValidationError("O pedido precisa ter ao menos um item.")
        return itens

    def create(self, validated_data):
        itens_data = validated_data.pop("itens")
        comprador = self.context["request"].user
        with transaction.atomic():
            pedido = Pedido.objects.create(comprador=comprador, **validated_data)
            for item in itens_data:
                produto = Produto.objects.select_for_update().get(pk=item["produto"].pk)
                if produto.estoque < item["quantidade"]:
                    raise serializers.ValidationError(
                        {"itens": f'Estoque insuficiente para "{produto.nome}".'}
                    )
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=item["quantidade"],
                    preco_unitario=produto.preco,
                )
                Produto.objects.filter(pk=produto.pk).update(
                    estoque=F("estoque") - item["quantidade"]
                )
        return pedido
