from decimal import Decimal, InvalidOperation

from django.db.models import Avg, F
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .models import Avaliacao, ItemPedido, Pedido, Produto
from .serializers import AvaliacaoSerializer, PedidoSerializer, ProdutoSerializer


class ProdutoListCreateView(generics.ListCreateAPIView):
    serializer_class = ProdutoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Produto.objects.select_related("categoria").annotate(
            media_avaliacoes=Avg("avaliacoes__nota")
        ).order_by("nome")
        categoria = self.request.query_params.get("categoria")
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        busca = self.request.query_params.get("busca")
        if busca:
            queryset = queryset.filter(nome__icontains=busca)
        preco_minimo = self.request.query_params.get("preco_minimo")
        if preco_minimo:
            try:
                preco_minimo = Decimal(preco_minimo)
            except InvalidOperation as error:
                raise ValidationError({"preco_minimo": "Informe um número válido."}) from error
            if preco_minimo < 0:
                raise ValidationError({"preco_minimo": "O preço não pode ser negativo."})
            queryset = queryset.filter(preco__gte=preco_minimo)
        else:
            preco_minimo = None
        preco_maximo = self.request.query_params.get("preco_maximo")
        if preco_maximo:
            try:
                preco_maximo = Decimal(preco_maximo)
            except InvalidOperation as error:
                raise ValidationError({"preco_maximo": "Informe um número válido."}) from error
            if preco_maximo < 0:
                raise ValidationError({"preco_maximo": "O preço não pode ser negativo."})
            if preco_minimo and preco_maximo < preco_minimo:
                raise ValidationError(
                    {"preco_maximo": "Deve ser maior ou igual ao preço mínimo."}
                )
            queryset = queryset.filter(preco__lte=preco_maximo)
        if self.request.query_params.get("disponivel") == "true":
            queryset = queryset.filter(estoque__gt=0)
        return queryset

    def perform_create(self, serializer):
        serializer.save(vendedor=self.request.user)


class PedidoCreateView(generics.CreateAPIView):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]


class AvaliacaoListCreateView(generics.ListCreateAPIView):
    serializer_class = AvaliacaoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Avaliacao.objects.filter(
            produto_id=self.kwargs["produto_id"]
        ).select_related("usuario")

    def perform_create(self, serializer):
        produto_id = self.kwargs["produto_id"]
        compra_concluida = ItemPedido.objects.filter(
            produto_id=produto_id,
            pedido__comprador=self.request.user,
            pedido__status__in=("PAGO", "ENVIADO"),
        ).exists()
        if not compra_concluida:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Apenas compradores com pedido pago ou enviado podem avaliar."
            )
        serializer.save(produto_id=produto_id, usuario=self.request.user)
