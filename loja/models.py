from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Categoria(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Produto(models.Model):
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="produtos"
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="produtos"
    )
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    estoque = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Pedido(models.Model):
    STATUS_CHOICES = [
        ("ABERTO", "Aberto"),
        ("PAGO", "Pago"),
        ("ENVIADO", "Enviado"),
        ("CANCELADO", "Cancelado"),
    ]
    comprador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pedidos"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ABERTO")
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum((item.subtotal for item in self.itens.all()), start=0)

    def __str__(self):
        return f"Pedido #{self.pk} de {self.comprador}"


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f"{self.quantidade}x {self.produto}"


class Avaliacao(models.Model):
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    nota = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comentario = models.TextField(blank=True, max_length=1000)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["produto", "usuario"], name="uma_avaliacao_por_usuario_produto"
            )
        ]

    def __str__(self):
        return f"{self.nota}/5 - {self.produto}"
