import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from loja.models import Categoria, Produto

User = get_user_model()


class Command(BaseCommand):
    help = "Adiciona produtos de demonstração sem alterar contas ou pedidos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vendor-username",
            help="Atribui todos os produtos ao usuário staff indicado.",
        )

    def handle(self, *args, **options):
        vendedores = User.objects.filter(is_active=True, is_staff=True)
        username = options["vendor_username"]
        if username:
            vendedores = vendedores.filter(username=username)
        vendedores = list(vendedores)
        if not vendedores:
            raise CommandError(
                "Nenhum usuário staff ativo foi encontrado para associar os "
                "produtos. Crie ou informe um usuário existente com "
                "--vendor-username."
            )

        with transaction.atomic():
            categorias = [
                Categoria.objects.get_or_create(nome=nome)[0]
                for nome in (
                    "Eletrônicos",
                    "Casa",
                    "Esportes",
                    "Livros",
                    "Beleza",
                    "Acessórios",
                )
            ]
            demo_products_count = Produto.objects.filter(
                descricao__startswith="Produto de demonstração "
            ).count()
            for index in range(demo_products_count + 1, 51):
                categoria = random.choice(categorias)
                Produto.objects.create(
                    vendedor=random.choice(vendedores),
                    categoria=categoria,
                    nome=f"{categoria.nome} Demo {index:02}",
                    descricao=(
                        f"Produto de demonstração {index} para o catálogo "
                        "do marketplace."
                    ),
                    preco=Decimal(random.randint(2500, 45000)) / 100,
                    estoque=random.randint(5, 28),
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Produtos demo verificados: "
                f"{Produto.objects.filter(descricao__startswith='Produto de demonstração ').count()}."
            )
        )
