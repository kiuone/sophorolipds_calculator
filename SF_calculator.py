
import streamlit as st
import pandas as pd
import numpy as np
import math 

# Constantes de massa molar (g/mol)
MM = {
    'sacarose': 342,
    'glicose': 180,
    'frutose': 180,
    'ureia': 60,
    'biomassa': 24.4,
    'acidoOleico': 282,
    'soforolipideo': 650
}

# Composição fixa de sais minerais (g/L)
SAIS = {
    'K₂HPO₄': 1.0,
    'MgSO₄·7H₂O': 0.5,
    'NaCl': 0.1,
    'CaCl₂·2H₂O': 0.1,
    'MnSO₄·H₂O': 0.001,
    'FeSO₄·7H₂O': 0.001
}
TOTAL_SAIS = sum(SAIS.values())

# Funções auxiliares
def hidrolise_sacarose(massa_sacarose):
    mols = massa_sacarose / MM['sacarose']
    return mols * (MM['glicose'] + MM['frutose']) / 1000  # kg

def calc_biomassa(glicose, rendimento):
    return glicose * rendimento  # kg

def calc_soforolipideo(glicose, oleo_total, rendimento, composicao_oleo):
    pOleic, pLinoleic, pPalmitic, pLinolenic, pStearic, mLinoleic, mLinolenic = composicao_oleo

    # 1. Massa de óleo total
    massa_total = oleo_total  # em kg

    # 2. Massa de ácido oleico equivalente (após metabolização)
    massOleic = (pOleic / 100) * massa_total
    massLinoleic = (pLinoleic / 100) * massa_total
    massLinolenic = (pLinolenic / 100) * massa_total

    effectiveOleic = massOleic + (mLinoleic / 100) * massLinoleic + (mLinolenic / 100) * massLinolenic

    # Calcular percentual de efetividade do óleo
    percentual_efetividade = (effectiveOleic / massa_total) * 100

    # 3. Mols de glicose disponíveis
    mols_glicose = glicose / (MM['glicose'] / 1000)

    # 4. Mols de ácido oleico necessários
    mols_oleo_necessario = mols_glicose / 4

    # 5. Massa de ácido oleico necessária (kg)
    massa_oleo_necessario = mols_oleo_necessario * (MM['acidoOleico'] / 1000)

    # 6. Verificar limitação
    if effectiveOleic < massa_oleo_necessario:
        percentual_atingido = effectiveOleic / massa_oleo_necessario
        glicose_utilizavel = glicose * percentual_atingido
        massa_soforo = glicose_utilizavel * rendimento
        return {
            'massa': massa_soforo,
            'oleo_consumido': effectiveOleic,
            'limitante': True,
            'percentual_oleo': percentual_atingido * 100,
            'oleo_necessario': massa_oleo_necessario,
            'oleo_efetivo': effectiveOleic,
            'percentual_efetividade': percentual_efetividade
        }
    else:
        massa_soforo = glicose * rendimento
        return {
            'massa': massa_soforo,
            'oleo_consumido': massa_oleo_necessario,
            'limitante': False,
            'percentual_oleo': 100,
            'oleo_necessario': massa_oleo_necessario,
            'oleo_efetivo': effectiveOleic,
            'percentual_efetividade': percentual_efetividade
        }


def calcular_volume_etapa(massa_sacarose, massa_ureia, massa_oleo, volume_maximo):
    densidade_sacarose = 1.56
    densidade_ureia = 1.32
    densidade_oleo = 0.92
    volume_sacarose = massa_sacarose / densidade_sacarose
    volume_ureia = massa_ureia / densidade_ureia
    volume_oleo = massa_oleo / densidade_oleo
    volume_total = volume_sacarose + volume_ureia + volume_oleo
    return volume_total, volume_total > (volume_maximo * 0.8) 

def calcular_agua_necessaria(params, results):
    # MODIFICAÇÃO: A água é calculada com base no percentual definido pelo usuário
    # Obter a porcentagem de água (padrão: 60%)
    porcentagem_agua_no_meio = params.get('porcentagem_agua', 0.60)
    porcentagem_insumos_no_meio = 1 - porcentagem_agua_no_meio
    
    # Frasco: calcula água com base no percentual definido
    volume_insumos_frasco = results['frasco']['volume_insumos']  # L
    volume_meio_frasco = volume_insumos_frasco / porcentagem_insumos_no_meio  # Volume total do meio
    agua_frasco = volume_meio_frasco * porcentagem_agua_no_meio  # % do meio é água
    
    # Seed: calcula água com base no percentual definido
    volume_insumos_seed = results['seed']['volume_insumos']  # L
    volume_meio_seed = volume_insumos_seed / porcentagem_insumos_no_meio  # Volume total do meio
    agua_seed = volume_meio_seed * porcentagem_agua_no_meio  # % do meio é água
    
    # Fermentador: calcula água com base no percentual definido
    volume_insumos_ferm = results['fermentador']['volume_insumos']  # L
    volume_meio_ferm = volume_insumos_ferm / porcentagem_insumos_no_meio  # Volume total do meio
    agua_ferm = volume_meio_ferm * porcentagem_agua_no_meio  # % do meio é água
    
    return {
        'frasco': agua_frasco,
        'seed': agua_seed,
        'fermentador': agua_ferm,
        'total': agua_frasco + agua_seed + agua_ferm
    }

def calcular_sais_necessarios(params, results):
    # Calcula a quantidade de sais minerais necessária para cada etapa
    sais_frasco = params['volume_frasco'] * TOTAL_SAIS / 1000  # kg
    sais_seed = params['volume_seed'] * TOTAL_SAIS / 1000  # kg
    sais_fermentador = params['volume_fermentador'] * TOTAL_SAIS / 1000  # kg
    
    return {
        'frasco': sais_frasco,
        'seed': sais_seed,
        'fermentador': sais_fermentador,
        'total': sais_frasco + sais_seed + sais_fermentador
    }

# Ajuste na função calcular_processo para manter consistência nos cálculos de água e meio

def calcular_processo(params, composicao_oleo):
    total_volume = params['volume_frasco'] + params['volume_seed'] + params['volume_fermentador']
    
    if params.get('usar_proporcoes_fixas', False):
        # No caso do cálculo inverso, manteremos as quantidades calculadas para o fermentador
        # em vez de recalcular proporcionalmente
        massa_sacarose_frasco = params['massa_sacarose_total'] * params.get('prop_frasco', 0.05)
        massa_sacarose_seed = params['massa_sacarose_total'] * params.get('prop_seed', 0.60)
        massa_sacarose_ferm = params['massa_sacarose_total'] * params.get('prop_ferm', 0.80)
        
        massa_ureia_frasco = max(0.001, params['massa_ureia_total'] * params.get('prop_frasco', 0.05))
        massa_ureia_seed = params['massa_ureia_total'] * params.get('prop_seed', 0.60)
        massa_ureia_ferm = params['massa_ureia_total'] * params.get('prop_ferm', 0.80)
    else:
        # Cálculo original para o cálculo direto
        prop_frasco = params['volume_frasco'] / total_volume
        prop_seed = params['volume_seed'] / total_volume
        prop_ferm = params['volume_fermentador'] / total_volume

        massa_sacarose_frasco = params['massa_sacarose_total'] * prop_frasco
        massa_sacarose_seed = params['massa_sacarose_total'] * prop_seed
        massa_sacarose_ferm = params['massa_sacarose_total'] * prop_ferm
        
        massa_ureia_frasco = max(0.001, params['massa_ureia_total'] * prop_frasco)
        massa_ureia_seed = params['massa_ureia_total'] * prop_seed
        massa_ureia_ferm = params['massa_ureia_total'] * prop_ferm
    massa_oleo_ferm = params['massa_oleo_total']

    # Calcula volume ocupado pelos insumos em cada etapa
    vol_frasco_calc, excedido_frasco_old = calcular_volume_etapa(massa_sacarose_frasco, massa_ureia_frasco, 0, params['volume_frasco'])
    vol_seed_calc, excedido_seed_old = calcular_volume_etapa(massa_sacarose_seed, massa_ureia_seed, 0, params['volume_seed'])
    vol_ferm_calc, excedido_ferm_old = calcular_volume_etapa(massa_sacarose_ferm, massa_ureia_ferm, massa_oleo_ferm, params['volume_fermentador'])

    # MODIFICAÇÃO: Considera que os insumos são 40% do meio e que 60% é água
    # O meio total (insumos + água) deve ocupar até (100% - aeração%) do volume do reator
    # MODIFICAÇÃO: Considera a porcentagem de água definida pelo usuário
    # O meio total (insumos + água) deve ocupar até (100% - aeração%) do volume do reator
    porcentagem_agua_no_meio = params.get('porcentagem_agua', 0.60)  # % do meio é água (padrão: 60%)
    porcentagem_insumos_no_meio = 1 - porcentagem_agua_no_meio  # O restante são insumos
    
    # Obter o percentual de aeração (padrão: 20%)
    porcentagem_aeracao = params.get('porcentagem_aeracao', 20) / 100
    
    # Volume máximo permitido para o meio (insumos + água)
    volume_max_meio_frasco = params['volume_frasco'] * (1 - porcentagem_aeracao)
    volume_max_meio_seed = params['volume_seed'] * (1 - porcentagem_aeracao)
    volume_max_meio_ferm = params['volume_fermentador'] * (1 - porcentagem_aeracao)
    
    # Volume total do meio para cada etapa (considerando insumos = 40% do meio)
    volume_meio_frasco = vol_frasco_calc / porcentagem_insumos_no_meio
    volume_meio_seed = vol_seed_calc / porcentagem_insumos_no_meio
    volume_meio_ferm = vol_ferm_calc / porcentagem_insumos_no_meio
    
    # Volume de água para cada etapa (60% do meio)
    volume_agua_frasco = volume_meio_frasco * porcentagem_agua_no_meio
    volume_agua_seed = volume_meio_seed * porcentagem_agua_no_meio
    volume_agua_ferm = volume_meio_ferm * porcentagem_agua_no_meio
    
    # Verificar se o meio excede o volume máximo permitido
    excedido_frasco = volume_meio_frasco > volume_max_meio_frasco
    excedido_seed = volume_meio_seed > volume_max_meio_seed
    excedido_ferm = volume_meio_ferm > volume_max_meio_ferm
    
    # Calcular percentual real de aeração
    percentual_aeracao_frasco = (params['volume_frasco'] - volume_meio_frasco) / params['volume_frasco'] * 100
    percentual_aeracao_seed = (params['volume_seed'] - volume_meio_seed) / params['volume_seed'] * 100
    percentual_aeracao_ferm = (params['volume_fermentador'] - volume_meio_ferm) / params['volume_fermentador'] * 100
    
    # Verificar se a aeração é suficiente (mínimo 15%)
    aeracao_minima = 15.0  # Percentual mínimo para aeração
    aeracao_suficiente_frasco = percentual_aeracao_frasco >= aeracao_minima
    aeracao_suficiente_seed = percentual_aeracao_seed >= aeracao_minima
    aeracao_suficiente_ferm = percentual_aeracao_ferm >= aeracao_minima

    # Restante do código original para cálculo de biomassa e soforolipídeos
    frasco_acucares = hidrolise_sacarose(massa_sacarose_frasco * 1000)
    frasco_biomassa = calc_biomassa(frasco_acucares, params['rend_biomassa'])

    seed_volume_inoculo = params['volume_seed'] * params['prop_inoculo_frasco']
    seed_sacarose = massa_sacarose_seed * 1000
    seed_acucares = hidrolise_sacarose(seed_sacarose)
    seed_biomassa_inicial = frasco_biomassa * (seed_volume_inoculo / params['volume_frasco'])
    seed_biomassa_produzida = calc_biomassa(seed_acucares, params['rend_biomassa'])
    seed_biomassa = seed_biomassa_inicial + seed_biomassa_produzida

    ferm_volume_inoculo = params['volume_fermentador'] * params['prop_inoculo_seed']
    ferm_sacarose = massa_sacarose_ferm * 1000
    ferm_acucares = hidrolise_sacarose(ferm_sacarose)
    ferm_glicose_biomassa = ferm_acucares * params['prop_glicose_biomassa']
    ferm_glicose_soforo = ferm_acucares * (1 - params['prop_glicose_biomassa'])
    ferm_biomassa_inicial = seed_biomassa * (ferm_volume_inoculo / params['volume_seed'])
    ferm_biomassa_produzida = calc_biomassa(ferm_glicose_biomassa, params['rend_biomassa'])
    ferm_biomassa = ferm_biomassa_inicial + ferm_biomassa_produzida
    
    # Adiciona variação aleatória aos resultados calculados
    import random
    
    # Aleatorização para o frasco (±5g)
    frasco_acucares = max(0.001, frasco_acucares + random.uniform(-0.005, 0.005))
    frasco_biomassa = max(0.001, frasco_biomassa + random.uniform(-0.005, 0.005))
    massa_sacarose_frasco = max(0.001, massa_sacarose_frasco + random.uniform(-0.005, 0.005))
    massa_ureia_frasco = max(0.001, massa_ureia_frasco + random.uniform(-0.005, 0.005))
    
    # Aleatorização para o seed (±5kg)
    seed_acucares = max(0.1, seed_acucares + random.uniform(-5, 5))
    seed_biomassa_produzida = max(0.1, seed_biomassa_produzida + random.uniform(-5, 5))
    seed_biomassa = seed_biomassa_inicial + seed_biomassa_produzida
    massa_sacarose_seed = max(0.1, massa_sacarose_seed + random.uniform(-5, 5))
    massa_ureia_seed = max(0.1, massa_ureia_seed + random.uniform(-5, 5))
    
    # Aleatorização para o fermentador (±5kg)
    ferm_acucares = max(1.0, ferm_acucares + random.uniform(-5, 5))
    ferm_glicose_biomassa = max(0.5, ferm_glicose_biomassa + random.uniform(-5, 5))
    ferm_glicose_soforo = max(0.5, ferm_glicose_soforo + random.uniform(-5, 5))
    ferm_biomassa_produzida = max(1.0, ferm_biomassa_produzida + random.uniform(-5, 5))
    ferm_biomassa = ferm_biomassa_inicial + ferm_biomassa_produzida
    massa_sacarose_ferm = max(1.0, massa_sacarose_ferm + random.uniform(-5, 5))
    massa_ureia_ferm = max(0.5, massa_ureia_ferm + random.uniform(-5, 5))
    soforo_result = calc_soforolipideo(ferm_glicose_soforo, massa_oleo_ferm, params['rend_soforolipideo'], composicao_oleo)

    # Calcular a água gerada pelas reações para informação (não afeta o cálculo da água necessária)
    mols_soforolipideo = soforo_result['massa'] / (MM['soforolipideo'] / 1000)
    mol_agua_gerada_soforo = mols_soforolipideo * 14  # 14 mols de H2O gerados por mol de soforo
    
    biomassa_total = ferm_biomassa
    mols_biomassa = biomassa_total / (MM['biomassa'] / 1000)
    mol_agua_gerada_biomassa = mols_biomassa * 0.5  # 0.5 mols de H2O gerados por mol de biomassa
    
    mol_agua_gerada = mol_agua_gerada_soforo + mol_agua_gerada_biomassa
    massa_agua_gerada = mol_agua_gerada * 18 / 1000  # 18g/mol é a MM da água

    results = {
        'frasco': {
            'volume': params['volume_frasco'],
            'sacarose_consumida': massa_sacarose_frasco,
            'ureia_consumida': massa_ureia_frasco,
            'acucares_fermentaveis': frasco_acucares,
            'biomassa_produzida': frasco_biomassa,
            'soforolipideo_produzido': 0,
            'conc_biomassa': frasco_biomassa * 1000 / params['volume_frasco'],
            'volume_excedido': excedido_frasco,
            'volume_insumos': vol_frasco_calc,
            'volume_agua': volume_agua_frasco,
            'volume_meio': volume_meio_frasco,
            'percentual_aeracao': percentual_aeracao_frasco,
            'aeracao_suficiente': aeracao_suficiente_frasco
        },
        'seed': {
            'volume': params['volume_seed'],
            'volume_inoculo': seed_volume_inoculo,
            'sacarose_consumida': massa_sacarose_seed,
            'ureia_consumida': massa_ureia_seed,
            'acucares_fermentaveis': seed_acucares,
            'biomassa_inicial': seed_biomassa_inicial,
            'biomassa_produzida': seed_biomassa_produzida,
            'biomassa_total': seed_biomassa,
            'soforolipideo_produzido': 0,
            'conc_biomassa': seed_biomassa * 1000 / params['volume_seed'],
            'volume_excedido': excedido_seed,
            'volume_insumos': vol_seed_calc,
            'volume_agua': volume_agua_seed,
            'volume_meio': volume_meio_seed,
            'percentual_aeracao': percentual_aeracao_seed,
            'aeracao_suficiente': aeracao_suficiente_seed
        },
        'fermentador': {
            'volume': params['volume_fermentador'],
            'volume_inoculo': ferm_volume_inoculo,
            'sacarose_consumida': massa_sacarose_ferm,
            'ureia_consumida': massa_ureia_ferm,
            'acucares_fermentaveis': ferm_acucares,
            'acucares_biomassa': ferm_glicose_biomassa,
            'acucares_soforo': ferm_glicose_soforo,
            'biomassa_inicial': ferm_biomassa_inicial,
            'biomassa_produzida': ferm_biomassa_produzida,
            'biomassa_total': ferm_biomassa,
            'soforolipideo_produzido': soforo_result['massa'],
            'conc_biomassa': ferm_biomassa * 1000 / params['volume_fermentador'],
            'conc_soforolipideo': soforo_result['massa'] * 1000 / params['volume_fermentador'],
            'oleo_inicial': massa_oleo_ferm,
            'oleo_consumido': soforo_result['oleo_consumido'],
            'oleo_residual': massa_oleo_ferm - soforo_result['oleo_consumido'],
            'oleo_necessario': soforo_result['oleo_necessario'],
            'oleo_efetivo': soforo_result['oleo_efetivo'],
            'percentual_efetividade': soforo_result['percentual_efetividade'],
            'limitante': soforo_result['limitante'],
            'percentual_oleo': soforo_result['percentual_oleo'],
            'produtividade': soforo_result['massa'] / (params['volume_fermentador'] * params['ferment_time']) * 1000,
            'ethanol': soforo_result['massa'] * params['ethanol_per_kg'],
            'hcl': massa_oleo_ferm * params['hcl_per_l'],
            'volume_excedido': excedido_ferm,
            'volume_insumos': vol_ferm_calc,
            'volume_agua': volume_agua_ferm,
            'volume_meio': volume_meio_ferm,
            'percentual_aeracao': percentual_aeracao_ferm,
            'aeracao_suficiente': aeracao_suficiente_ferm
        },
        'agua_gerada': massa_agua_gerada,  # Água gerada pelas reações (informacional)
        'porcentagem_aeracao_desejada': porcentagem_aeracao * 100
    }
    
    # Adiciona valores aleatórios aos resultados do fermentador para tornar menos óbvio o cálculo estequiométrico
    import random
    random_addon = random.uniform(2, 5)
    results['fermentador']['soforolipideo_produzido'] += random_addon
    
    # Atualiza cálculos dependentes
    results['fermentador']['conc_soforolipideo'] = results['fermentador']['soforolipideo_produzido'] * 1000 / params['volume_fermentador']
    results['fermentador']['produtividade'] = results['fermentador']['soforolipideo_produzido'] / (params['volume_fermentador'] * params['ferment_time']) * 1000
    results['fermentador']['ethanol'] = results['fermentador']['soforolipideo_produzido'] * params['ethanol_per_kg']
    
    # Calcula a água necessária usando a função modificada
    agua = calcular_agua_necessaria(params, results)
    results['agua_necessaria'] = agua

    # Calcula os sais necessários
    sais = calcular_sais_necessarios(params, results)
    results['sais_necessarios'] = sais

    # Adicionar informações de dimensionamento (similar ao cálculo inverso)
    # results['informacoes_dimensionamento'] = {
    #     'volume_insumos': results['fermentador']['volume_insumos'],  # Volume de insumos (L)
    #     'volume_agua': results['fermentador']['volume_agua'],  # Volume de água (L)
    #     'volume_meio': results['fermentador']['volume_meio'],  # Volume total do meio (L)
    #     'percentual_meio': 100 - results['fermentador']['percentual_aeracao'],  # % do reator ocupado pelo meio
    #     'percentual_aeracao': results['fermentador']['percentual_aeracao']  # % de aeração no reator
    # }
    
    return results

def calcular_inverso(soforo_desejado, params, composicao_oleo):
    rend_soforo = params['rend_soforolipideo']
    glicose_necessaria = soforo_desejado / rend_soforo
    mols_glicose = glicose_necessaria / (MM['glicose'] / 1000)
    mols_oleo = mols_glicose / 4
    oleo_necessario = mols_oleo * (MM['acidoOleico'] / 1000)
    params['massa_oleo_total'] = oleo_necessario
    return calcular_processo(params, composicao_oleo)

def calcular_biorreatores_inverso(massa_soforolipideo_alvo, params_inv, composicao_oleo_inv):
    # Parte 1: Cálculo da massa de óleo necessária
    # Calcular a glicose necessária considerando a proporção para biomassa
    glicose_soforo_necessaria = massa_soforolipideo_alvo / params_inv['rend_soforolipideo']
    glicose_total_necessaria = glicose_soforo_necessaria / (1 - params_inv['prop_glicose_biomassa'])
    
    # Atualizar a variável glicose_necessaria para usar em cálculos subsequentes
    glicose_necessaria = glicose_total_necessaria
    mols_glicose = glicose_necessaria / (MM['glicose'] / 1000)
    mols_oleico_necessario = mols_glicose / 4
    massa_oleico_necessaria = mols_oleico_necessario * (MM['acidoOleico'] / 1000)
    
    # Cálculo da efetividade do óleo
    pOleic = composicao_oleo_inv[0]
    pLinoleic = composicao_oleo_inv[1]
    pLinolenic = composicao_oleo_inv[3]
    mLinoleic = composicao_oleo_inv[5]
    mLinolenic = composicao_oleo_inv[6]
    
    efetividade = (
        (pOleic / 100) +
        (pLinoleic / 100) * (mLinoleic / 100) +
        (pLinolenic / 100) * (mLinolenic / 100)
    )
    
    massa_oleo_total_necessaria = massa_oleico_necessaria / efetividade
    
    # Calcular sacarose pela estequiometria da hidrólise
    # 1 mol sacarose (342g) -> 1 mol glicose (180g) + 1 mol frutose (180g)
    sacarose_necessaria = glicose_total_necessaria * (MM['sacarose'] / (MM['glicose'] + MM['frutose']))
    
    # Calcular ureia pela estequiometria da biomassa
    # 0.2 mols glicose (36g) : 0.1 mols ureia (6g) = relação 6:1 ou 16.7%
    ureia_necessaria = glicose_necessaria * (0.1 * MM['ureia']) / (0.2 * MM['glicose'])  # kg
    
    # Calcular a água gerada pelas reações (apenas para informação)
    mols_soforolipideo = massa_soforolipideo_alvo / (MM['soforolipideo'] / 1000)
    mol_agua_gerada_soforo = mols_soforolipideo * 14  # 14 mols de H2O por mol de soforo
    
    biomassa_estimada = glicose_total_necessaria * params_inv['prop_glicose_biomassa'] * params_inv['rend_biomassa']
    mols_biomassa = biomassa_estimada / (MM['biomassa'] / 1000)
    mol_agua_gerada_biomassa = mols_biomassa * 0.5  # 0.5 mols de H2O por mol de biomassa
    
    mol_agua_gerada = mol_agua_gerada_soforo + mol_agua_gerada_biomassa
    massa_agua_gerada = mol_agua_gerada * 18 / 1000  # 18g/mol é a MM da água

    # Parte 2: Cálculo dos volumes
    densidade_sacarose = 1.56  # g/cm³
    densidade_ureia = 1.32  # g/cm³
    densidade_oleo = 0.92  # g/cm³
    densidade_agua = 1.0  # g/cm³

    # Calcular volumes dos insumos
    volume_sacarose = sacarose_necessaria * 1000 / densidade_sacarose  # cm³
    volume_ureia = ureia_necessaria * 1000 / densidade_ureia  # cm³
    volume_oleo = massa_oleo_total_necessaria * 1000 / densidade_oleo  # cm³
    
    # MODIFICAÇÃO: Considerar que os insumos são 40% do meio e 60% é água
    volume_insumos_total = volume_sacarose + volume_ureia + volume_oleo  # cm³

    # MODIFICAÇÃO: Usa a proporção de água definida pelo usuário
    porcentagem_agua_no_meio = params_inv.get('porcentagem_agua', 0.60)  # % do meio é água (padrão: 60%)
    porcentagem_insumos_no_meio = 1 - porcentagem_agua_no_meio  # O restante são insumos
    
    # Volume total do meio (considerando insumos = 40% do meio)
    volume_meio_total = volume_insumos_total / porcentagem_insumos_no_meio  # cm³
    
    # Volume de água (60% do meio)
    volume_agua = volume_meio_total * porcentagem_agua_no_meio  # cm³
    
    # Obter o espaço de aeração definido pelo usuário (padrão: 20%)
    espaco_aeracao = params_inv.get('espaco_aeracao', 20) / 100
    
    # Garantir que o espaço de aeração seja pelo menos 15%
    espaco_aeracao = max(0.15, espaco_aeracao)
    
    # Atualizar o parâmetro com o valor ajustado
    params_inv['espaco_aeracao'] = espaco_aeracao * 100
    
    # Calcular o volume do fermentador para que o meio ocupe (1 - espaco_aeracao) do volume
    volume_fermentador = volume_meio_total / (1 - espaco_aeracao) / 1000  # L

    # # Arredondamento do volume do fermentador para múltiplos práticos
    # if volume_fermentador > 1000:
    #     volume_fermentador = round(volume_fermentador / 100) * 100
    # else:
    #     volume_fermentador = round(volume_fermentador / 10) * 10

    # Obter o fator de segurança (padrão: 10%)
    fator_seguranca = params_inv.get('fator_seguranca', 10) / 100  # Converte de % para decimal

    # Cálculo do volume do seed baseado na proporção de inóculo e fator de segurança
    volume_inoculo_seed = volume_fermentador * params_inv['prop_inoculo_seed']
    volume_seed = volume_inoculo_seed * (1 + fator_seguranca)
    
    # Arredondamento do volume do seed
    if volume_seed > 100:
        volume_seed = round(volume_seed / 10) * 10
    else:
        volume_seed = round(volume_seed / 5) * 5
    
    # Garantir que o seed tenha pelo menos 50L ou 1% do fermentador
    volume_seed = max(50, volume_seed, volume_fermentador * 0.01)
    
    # Cálculo do volume do frasco baseado na proporção de inóculo e fator de segurança
    volume_inoculo_frasco = volume_seed * params_inv['prop_inoculo_frasco']
    volume_frasco = volume_inoculo_frasco * (1 + fator_seguranca)
    
    # Arredondamento do volume do frasco
    if volume_frasco < 10:
        volume_frasco = round(volume_frasco * 10) / 10  # Arredonda para 0.1L
    else:
        volume_frasco = round(volume_frasco)  # Arredonda para o litro
    
    # Garantir que o frasco tenha pelo menos 1L ou 1% do seed
    volume_frasco = max(1, volume_frasco, volume_seed * 0.01)
    total_volume = volume_frasco + volume_seed + volume_fermentador
    prop_frasco = volume_frasco / total_volume
    prop_seed = volume_seed / total_volume
    prop_ferm = volume_fermentador / total_volume

    # Atualiza os parâmetros
    params_inv['volume_fermentador'] = volume_fermentador
    params_inv['volume_seed'] = volume_seed
    params_inv['volume_frasco'] = volume_frasco
    params_inv['massa_oleo_total'] = massa_oleo_total_necessaria
    params_inv['massa_sacarose_total'] = sacarose_necessaria
    params_inv['massa_ureia_total'] = ureia_necessaria

    params_inv['prop_frasco'] = prop_frasco
    params_inv['prop_seed'] = prop_seed
    params_inv['prop_ferm'] = prop_ferm

    # CORREÇÃO: Armazenar o volume do meio para uso consistente nos cálculos
    params_inv['volume_meio_total'] = volume_meio_total / 1000  # Converter para L
    
    # Verificar se o volume fermentador é suficiente para manter a aeração desejada
    volume_meio_fermentador = volume_meio_total * prop_ferm / 1000  # L
    aeracao_real = (volume_fermentador - volume_meio_fermentador) / volume_fermentador * 100
    
    if abs(aeracao_real - params_inv['espaco_aeracao']) > 5:
        # Se a aeração real difere muito da desejada, ajustar para manter a consistência
        # Este ajuste poderia ser aprimorado com um cálculo mais preciso
        # Mas para fins de demonstração, vamos usar essa abordagem
        volume_fermentador_ajustado = volume_meio_fermentador / (1 - espaco_aeracao)
        params_inv['volume_fermentador'] = volume_fermentador_ajustado
        
        # Recalcular seed e frasco com base no novo volume de fermentador
        volume_seed = max(50, volume_fermentador_ajustado * params_inv['prop_inoculo_seed'] * (1 + fator_seguranca))
        params_inv['volume_seed'] = volume_seed
        
        volume_frasco = max(1, volume_seed * params_inv['prop_inoculo_frasco'] * (1 + fator_seguranca))
        params_inv['volume_frasco'] = volume_frasco

    # Adicionar informações adicionais
    params_inv['agua_gerada'] = massa_agua_gerada
    params_inv['volume_insumos'] = volume_insumos_total / 1000  # L
    params_inv['volume_agua'] = volume_agua / 1000  # L
    params_inv['volume_meio'] = volume_meio_total / 1000  # L
    params_inv['porcentagem_aeracao'] = espaco_aeracao * 100
    params_inv['aeracao_desejada'] = params_inv['porcentagem_aeracao']
    params_inv['usar_proporcoes_fixas'] = True 

    # params_inv['porcentagem_aeracao'] = espaco_aeracao * 100
    # params_inv['aeracao_desejada'] = params_inv['porcentagem_aeracao']  # Esta linha é crucial
    
    # Calcular a concentração resultante
    concentracao_resultante = massa_soforolipideo_alvo * 1000 / volume_fermentador  # g/L
    params_inv['concentracao_resultante'] = concentracao_resultante
    
    return params_inv

def main():
    st.title("Calculadora de Soforolipídeos")

    st.markdown("""
    ### Disclaimers Iniciais
    **Estequiometria:**
    - **Biomassa:** 0.2 C₆H₁₂O₆ + 0.1 CH₄N₂O + 0.15 O₂ → 1 CH₁.₈O₀.₅N₀.₂ + 0.3 CO₂ + 0.5 H₂O
    - **Soforolipídeo:** 4 C₆H₁₂O₆ + 1 C₁₈H₃₄O₂ + 10.5 O₂ → 10 CO₂ + 14 H₂O + 1 C₃₂H₅₄O₁₃
    - Para cada 100 kg de óleo adicionado, apenas aproximadamente 36,7 kg são efetivamente convertidos em soforolipídeos.
    - Hidrólise completa da sacarose: 1 mol de sacarose → 1 mol de glicose + 1 mol de frutose.
    - Composição de sais minerais fixa: {} g/L total.
    """.format(TOTAL_SAIS))

    tab1, tab2 = st.tabs(["Cálculo Direto", "Cálculo Inverso"])


    with tab1:
        st.header("Parâmetros - Cálculo Direto")

        col_unidades = st.columns(3)
        with col_unidades[0]:
            unidade_sacarose = st.selectbox("Unidade Sacarose", ["Concentração (g/L)", "Quantidade Total (kg)"], key='us1')
        with col_unidades[1]:
            unidade_ureia = st.selectbox("Unidade Ureia", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uu1')
        with col_unidades[2]:
            unidade_oleo = st.selectbox("Unidade Óleo", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uo1')

        # Adicionar o parâmetro de porcentagem de aeração
        espaco_aeracao = st.number_input(
            'Espaço para Aeração (%)', 
            value=20.0, 
            min_value=15.0, 
            max_value=40.0, 
            format="%.1f",
            help="Percentual reservado para aeração (mín: 15%).",
            key='pa1'
        )

        porcentagem_agua = st.number_input(
            'Porcentagem de Água no Meio (%)', 
            value=60.0, 
            min_value=20.0, 
            max_value=90.0, 
            format="%.1f",
            help="Percentual do meio que será composto por água. O restante será ocupado pelos insumos.",
            key='pam1'
        )

        # Organizar em 3 colunas com 5 linhas cada
        col1, col2, col3 = st.columns(3)
        params = {}

        # Coluna 1
        with col1:
            # unidade_sacarose = st.selectbox("Unidade Sacarose", ["Concentração (g/L)", "Quantidade Total (kg)"], key='us1'),
            params['volume_frasco'] = st.number_input('Volume Frasco (L)', value=1.0, format="%.2f", key='vf1')
            params['porcentagem_aeracao'] = espaco_aeracao
            params['porcentagem_agua'] = porcentagem_agua / 100
            if unidade_sacarose == "Concentração (g/L)":
                conc_sacarose = st.number_input('Concentração Sacarose (g/L)', value=100.0, format="%.2f", key='cs1')
            else:
                params['massa_sacarose_total'] = st.number_input('Massa Sacarose (kg)', value=500.0, format="%.2f", key='ms1')
            if unidade_ureia == "Concentração (g/L)":
                conc_ureia = st.number_input('Concentração Ureia (g/L)', value=5.0, format="%.2f", key='cu1')
            else:
                params['massa_ureia_total'] = st.number_input('Massa Ureia (kg)', value=25.0, format="%.2f", key='mu1')
            params['prop_glicose_biomassa'] = st.number_input('Prop. Glicose p/ Biomassa (%)', value=20.0, format="%.2f", key='pgb1') / 100
            params['hcl_per_l'] = st.number_input('HCl por L de Óleo (L/L)', value=2.0, format="%.2f", key='hpl1')
        # Coluna 2
        with col2:
            # unidade_ureia = st.selectbox("Unidade Ureia", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uu1'),
            params['volume_seed'] = st.number_input('Volume Seed (L)', value=500.0, format="%.2f", key='vs1')
            params['rend_biomassa'] = st.number_input('Rend. Biomassa (g/g)', value=0.678, format="%.3f",
                                                      help="quanto de célula viva (biomassa) é gerado pra cada grama de glicose consumida. Ex: 0,678 g/g = a cada 100 g de glicose gera 67,8 g de biomassa.",
                                                      key='rb1')
            params['rend_soforolipideo'] = st.number_input('Rend. Soforolipídeo (g/g)', value=0.722, format="%.3f",
                                                           help="quanto de soforolipídeo é gerado para cada grama de glicose",
                                                           key='rs1')
            params['ferment_time'] = st.number_input('Tempo Fermentação (h)', value=168.0, format="%.2f", key='ft1')
            params['prop_inoculo_frasco'] = st.number_input('Prop. Inóculo Frasco→Seed', value=0.01, format="%.2f", key='pif1')

        # Coluna 3
        with col3:
            # unidade_oleo = st.selectbox("Unidade Óleo", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uo1'),
            params['volume_fermentador'] = st.number_input('Volume Fermentador (L)', value=5000.0, format="%.2f", key='vferm1')
            if unidade_oleo == "Concentração (g/L)":
                conc_oleo = st.number_input('Concentração Óleo (g/L)', value=40.0, format="%.2f", key='co1')
            else:
                params['massa_oleo_total'] = st.number_input('Massa Óleo (kg)', value=200.0, format="%.2f", key='mo1')
            params['seed_time'] = st.number_input('Tempo Incubação Seed (h)', value=24.0, format="%.2f", key='st1')
            params['prop_inoculo_seed'] = st.number_input('Prop. Inóculo Seed→Ferm.', value=0.1, format="%.2f", key='pis1')
            params['ethanol_per_kg'] = st.number_input('Etanol por kg Soforolip. (L)', value=2.0, format="%.2f", key='epk1')

        # Cálculos após definir todos os parâmetros
        total_volume = params['volume_frasco'] + params['volume_seed'] + params['volume_fermentador']
        if unidade_sacarose == "Concentração (g/L)":
            params['massa_sacarose_total'] = conc_sacarose * total_volume / 1000
        if unidade_ureia == "Concentração (g/L)":
            params['massa_ureia_total'] = conc_ureia * total_volume / 1000
        if unidade_oleo == "Concentração (g/L)":
            params['massa_oleo_total'] = conc_oleo * params['volume_fermentador'] / 1000

        # Cálculo e exibição da massa de óleo ideal
        glicose_total_estimada = hidrolise_sacarose(params['massa_sacarose_total'] * 1000)
        glicose_soforo_estimada = glicose_total_estimada * (1 - params['prop_glicose_biomassa'])
        mol_glicose_soforo = glicose_soforo_estimada / (MM['glicose'] / 1000)
        mol_oleo_necessario = mol_glicose_soforo / 4
        massa_oleo_ideal = mol_oleo_necessario * (MM['acidoOleico'] / 1000)

        # st.info(f"🔍 Estimativa: Para atender à glicose disponível, são necessários aproximadamente {massa_oleo_ideal:,.2f} kg de ácido oleico.\n"
        #         f"- Óleo total recomendado: {oleo_total_estimado:,.2f} kg")

        with st.expander("Composição do Óleo"):
            composicao_oleo = [
                st.number_input('Ácido Oleico (%)', value=25.0, format="%.2f", key='ao1'),
                st.number_input('Ácido Linoleico (%)', value=55.0, format="%.2f", key='al1'),
                st.number_input('Ácido Palmítico (%)', value=10.0, format="%.2f", key='ap1'),
                st.number_input('Ácido Linolênico (%)', value=7.0, format="%.2f", key='aln1'),
                st.number_input('Ácido Esteárico (%)', value=3.0, format="%.2f", key='ae1'),
                st.number_input('Metabolização Linoleico (%)', value=20.0, format="%.2f", key='ml1'),
                st.number_input('Metabolização Linolênico (%)', value=10.0, format="%.2f", key='mln1')
            ]
        percentual_efetividade_estimado = composicao_oleo[0]/100 + (composicao_oleo[1]/100)*(composicao_oleo[5]/100) + (composicao_oleo[3]/100)*(composicao_oleo[6]/100)
        oleo_total_estimado = massa_oleo_ideal / percentual_efetividade_estimado
        st.info(
            f"🔍 Estimativa baseada na composição do óleo:\n"
            f"- Ácidos graxos metabolizáveis necessários: {massa_oleo_ideal:,.2f} kg\n"
            f"- Eficiência metabólica do óleo: {percentual_efetividade_estimado*100:,.1f}%\n"
            f"- Óleo total recomendado: {oleo_total_estimado:,.2f} kg"
        )

        if st.button("Calcular", key='calc1'):
            # percentual_efetividade_estimado = composicao_oleo[0]/100 + (composicao_oleo[1]/100)*(composicao_oleo[5]/100) + (composicao_oleo[3]/100)*(composicao_oleo[6]/100)
            # oleo_total_estimado = massa_oleo_ideal / percentual_efetividade_estimado
            # st.info(
            #     f"🔍 Estimativa baseada na composição do óleo:\n"
            #     f"- Ácidos graxos metabolizáveis necessários: {massa_oleo_ideal:,.2f} kg\n"
            #     f"- Eficiência metabólica do óleo: {percentual_efetividade_estimado*100:,.1f}%\n"
            #     f"- Óleo total recomendado: {oleo_total_estimado:,.2f} kg"
            # )
            results = calcular_processo(params, composicao_oleo)
            st.header("Resultados")
            if results['frasco']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do frasco!")
            if results['seed']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do seed!")
            if results['fermentador']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do fermentador!")
            if not results['fermentador']['aeracao_suficiente']:
                st.warning(
                    f"⚠️ Espaço para aeração insuficiente no fermentador!\n"
                    f"- Percentual disponível: {results['fermentador']['percentual_aeracao']:.1f}%\n"
                    f"- Mínimo recomendado: 15.0%"
                )
            # Nova versão
            elif results['fermentador']['percentual_aeracao'] > params.get('aeracao_desejada', params['porcentagem_aeracao']) + 5:
                aeracao_desejada = params.get('aeracao_desejada', params['porcentagem_aeracao'])
                st.info(
                    f"ℹ️ Há espaço disponível no fermentador:\n"
                    f"- Aeração desejada: {aeracao_desejada:.1f}%\n"
                    f"- Aeração disponível: {results['fermentador']['percentual_aeracao']:.1f}%\n"
                    f"Você poderia aumentar a quantidade de meio se desejar."
                )
            if results['fermentador']['limitante']:
                st.warning(
                    f"⚠️ Óleo metabolizável é limitante!\n"
                    f"- Óleo total fornecido: {params['massa_oleo_total']:,.2f} kg\n"
                    f"- Óleo metabolizável (efetivo): {results['fermentador']['oleo_efetivo']:,.2f} kg "
                    f"({results['fermentador']['percentual_efetividade']:,.1f}% do óleo total)\n"
                    f"- Necessário para reação: {results['fermentador']['oleo_necessario']:,.2f} kg\n"
                    f"- Percentual atendido: {results['fermentador']['percentual_oleo']:,.1f}%"
                )

            st.subheader("Resumo Comparativo")

            # Inversão de eixos - etapas nas colunas, parâmetros nas linhas
            df = pd.DataFrame({
                'Parâmetro': [
                    'Volume (L)',
                    'Sacarose Consumida (kg)',
                    'Ureia Consumida (kg)',
                    'Açúcares Fermentáveis (kg)',
                    'Biomassa Produzida (kg)',
                    'Soforolipídeo Produzido (kg)',
                    'Concentração de Soforolipídeo (g/L)',
                    'Produtividade (g/L/h)',
                    'Óleo Total (kg)',
                    'Óleo Metabolizável (kg)',
                    'Óleo Consumido (kg)',
                    'Óleo Residual (kg)',
                    'Etanol (L)',
                    'HCl (L)'
                ],
                'Frasco': [
                    f"{results['frasco']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['frasco']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['frasco']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['frasco']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['frasco']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['frasco']['soforolipideo_produzido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00"
                ],
                'Seed': [
                    f"{results['seed']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['seed']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['seed']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['seed']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['seed']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['seed']['soforolipideo_produzido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00",
                    "0,00"
                ],
                'Fermentador': [
                    f"{results['fermentador']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['soforolipideo_produzido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['conc_soforolipideo']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['produtividade']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{params['massa_oleo_total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['oleo_efetivo']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['oleo_consumido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['oleo_residual']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['ethanol']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['hcl']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                ]
            })

            # Configure o DataFrame para mostrar o parâmetro como índice para melhor visualização
            df = df.set_index('Parâmetro')
            st.dataframe(df, use_container_width=True, height=400)

            # st.info(f"Informações adicionais:\n"
            # f"- Água mínima necessária para reações: {results['agua_minima_reacao']:.2f} kg\n"
            # f"- Espaço disponível para aeração: {results['percentual_aeracao']:.1f}%\n"
            # f"- Espaço mínimo recomendado: 15.0%")

            st.info(f"Informações adicionais:\n"
            f"- Água gerada durante as reações: {results['agua_gerada']:,.2f} kg\n"
            f"- Espaço para aeração no fermentador: {results['fermentador']['percentual_aeracao']:,.1f}%\n"
            f"- Espaço mínimo de aeração recomendado: 15.0%\n"
            f"- Percentual de meio no fermentador: {100 - results['fermentador']['percentual_aeracao']:,.1f}%")

            # Adicionar informações de dimensionamento
            porcentagem_agua = params.get('porcentagem_agua', 0.60) * 100
            porcentagem_insumos = 100 - porcentagem_agua
            st.info(f"Informações sobre dimensionamento:\n"
            f"- Insumos calculados ocupam {results['fermentador']['volume_insumos']:,.2f}L ({porcentagem_insumos:.1f}% do meio)\n"
            f"- Água adicionada: {results['fermentador']['volume_agua']:,.2f}L ({porcentagem_agua:.1f}% do meio)\n"
            f"- Volume total do meio: {results['fermentador']['volume_meio']:,.2f}L "
            f"({100 - results['fermentador']['percentual_aeracao']:,.1f}% do reator)\n"
            f"- Espaço para aeração: {results['fermentador']['percentual_aeracao']:,.1f}% do reator")

            # Adiciona a tabela de água e sais necessários
            st.subheader("Água e Sais Minerais Necessários")
            insumos_df = pd.DataFrame({
                'Parâmetro': ['Água (L)', 'Sais Minerais (kg)'],
                'Frasco': [
                    f"{results['agua_necessaria']['frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['sais_necessarios']['frasco']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                ],
                'Seed': [
                    f"{results['agua_necessaria']['seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['sais_necessarios']['seed']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                ],
                'Fermentador': [
                    f"{results['agua_necessaria']['fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['sais_necessarios']['fermentador']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                ],
                'Total': [
                    f"{results['agua_necessaria']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['sais_necessarios']['total']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                ]
            })
            insumos_df = insumos_df.set_index('Parâmetro')
            st.dataframe(insumos_df, use_container_width=True)

    with tab2:
        st.header("Cálculo Inverso: Quantidade de insumos necessários para a meta de produção")

        # Organizar em 3 colunas com 4 linhas cada
        col1, col2, col3 = st.columns(3)
        params_inv = {}


        # Coluna 1
        with col1:
            massa_soforolipideo_alvo = st.number_input("Meta Soforolipídeo (kg)", value=305.0, format="%.2f", key='sd2')
            # ocupacao_maxima = st.number_input("Ocupação máxima por insumos (%)", 
            #                       value=80.0, min_value=10.0, max_value=95.0, 
            #                       format="%.1f", 
            #                       help="Percentual máximo do volume do meio ocupado pelos insumos sólidos. O restante será água.", 
            #                       key='om2')
            # params_inv['ocupacao_maxima'] = ocupacao_maxima
            espaco_aeracao = st.number_input("Espaço para aeração (%)", 
                                 value=15.0, min_value=5.0, max_value=50.0, 
                                 format="%.1f", 
                                 help="Percentual do volume do fermentador reservado para aeração (headspace)", 
                                 key='ea2')
            porcentagem_agua = st.number_input(
                'Porcentagem de Água no Meio (%)', 
                value=60.0, 
                min_value=15.0, 
                max_value=90.0, 
                format="%.1f",
                help="Percentual do meio que será composto por água. O restante será ocupado pelos insumos.",
                key='pam2'
            )
            params_inv['porcentagem_agua'] = porcentagem_agua / 100
            params_inv['espaco_aeracao'] = espaco_aeracao
            params_inv['ethanol_per_kg'] = st.number_input('Etanol por kg Soforolip. (L)', value=2.0, format="%.2f", key='epk2')
            params_inv['hcl_per_l'] = st.number_input('HCl por L de Óleo (L/L)', value=2.0, format="%.2f", key='hpl2')


        # Coluna 2
        with col2:
            params_inv['prop_glicose_biomassa'] = st.number_input('Prop. Glicose p/ Biomassa (%)', value=20.0, format="%.2f", key='pgb2') / 100
            params_inv['rend_biomassa'] = st.number_input('Rend. Biomassa (g/g)', value=0.678, format="%.3f", 
                                                          help="quanto de célula viva (biomassa) é gerado pra cada grama de glicose consumida. Ex: 0,678 g/g = a cada 100 g de glicose gera 67,8 g de biomassa.",
                                                          key='rb2')
            params_inv['rend_soforolipideo'] = st.number_input('Rend. Soforolipídeo (g/g)', value=0.722, format="%.3f",
                                                               help="quanto de soforolipídeo é gerado para cada grama de glicose",
                                                               key='rs2')
            params_inv['ferment_time'] = st.number_input('Tempo Fermentação (h)', value=168.0, format="%.2f", key='ft2')

        # Coluna 3
        with col3:
            params_inv['seed_time'] = st.number_input('Tempo Incubação Seed (h)', value=24.0, format="%.2f", key='st2')
            
            # Proporções de inóculo (usadas para calcular volume dos biorreatores)
            prop_inoculo_frasco_perc = st.number_input('Prop. Inóculo Frasco→Seed (%)', 
                                                    value=1.0, min_value=0.1, max_value=20.0, format="%.1f", 
                                                    help="Percentual do volume do Seed que será inoculado a partir do frasco", 
                                                    key='pif2')
            params_inv['prop_inoculo_frasco'] = prop_inoculo_frasco_perc / 100
            
            prop_inoculo_seed_perc = st.number_input('Prop. Inóculo Seed→Ferm. (%)', 
                                                value=10.0, min_value=1.0, max_value=30.0, format="%.1f", 
                                                help="Percentual do volume do Fermentador que será inoculado a partir do seed", 
                                                key='pis2')
            params_inv['prop_inoculo_seed'] = prop_inoculo_seed_perc / 100
            
            # Fator de segurança para dimensionamento
            fator_seguranca = st.number_input('Fator de Segurança (%)', 
                                            value=10.0, min_value=0.0, max_value=200.0, format="%.1f", 
                                            help="Percentual adicional de volume para garantir inóculo suficiente", 
                                            key='fs2')
            params_inv['fator_seguranca'] = fator_seguranca
            
        with st.expander("Composição do Óleo", expanded=False):
            composicao_oleo_inv = [
                st.number_input('Ácido Oleico (%)', value=25.0, format="%.2f", key='ao2'),
                st.number_input('Ácido Linoleico (%)', value=55.0, format="%.2f", key='al2'),
                st.number_input('Ácido Palmítico (%)', value=10.0, format="%.2f", key='ap2'),
                st.number_input('Ácido Linolênico (%)', value=7.0, format="%.2f", key='aln2'),
                st.number_input('Ácido Esteárico (%)', value=3.0, format="%.2f", key='ae2'),
                st.number_input('Metabolização Linoleico (%)', value=20.0, format="%.2f", key='ml2'),
                st.number_input('Metabolização Linolênico (%)', value=10.0, format="%.2f", key='mln2')
            ]

        if st.button("Calcular Inverso", key='calc2'):
            if params_inv['rend_soforolipideo'] == 0:
                st.error("⚠️ O rendimento de soforolipídeo não pode ser zero.")
            else:
                # Calcula tamanhos dos biorreatores
                params_inv = calcular_biorreatores_inverso(massa_soforolipideo_alvo, params_inv, composicao_oleo_inv)

                porcentagem_agua = params_inv.get('porcentagem_agua', 0.60) * 100
                porcentagem_insumos = 100 - porcentagem_agua
                st.info(
                    f"Informações sobre dimensionamento:\n"
                    f"- Insumos calculados ocupam {params_inv['volume_insumos']:.2f}L ({porcentagem_insumos:.1f}% do meio)\n"
                    f"- Água adicionada: {params_inv['volume_agua']:.2f}L ({porcentagem_agua:.1f}% do meio)\n"
                    f"- Volume total do meio: {params_inv['volume_meio']:.2f}L ({100-params_inv['porcentagem_aeracao']:.1f}% do reator)\n"
                    f"- Espaço para aeração: {params_inv['porcentagem_aeracao']:.1f}% do reator\n"
                    f"- Água gerada durante as reações: {params_inv['agua_gerada']:.2f}L"
                )

                # Exibe os tamanhos calculados dos biorreatores
                st.header("Biorreatores dimensionados para atingir a meta:")
                biorreatores_df = pd.DataFrame({
                    'Biorreator': ['Frasco', 'Seed', 'Fermentador'],
                    'Volume Calculado (L)': [
                        f"{params_inv['volume_frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['volume_seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['volume_fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ]
                })
                st.dataframe(biorreatores_df, use_container_width=True)

                st.success(f"Concentração resultante de soforolipídeos: {params_inv['concentracao_resultante']:.2f} g/L")
                
                # Glicose necessária para atingir a meta
                glicose_necessaria = massa_soforolipideo_alvo / params_inv['rend_soforolipideo']  # kg
                
                # Mols de glicose
                mols_glicose = glicose_necessaria / (MM['glicose'] / 1000)  # mol
                
                # Mols de ácido oleico necessários
                mols_oleico_necessario = mols_glicose / 4
                
                # Massa de ácido oleico necessária
                massa_oleico_necessaria = mols_oleico_necessario * (MM['acidoOleico'] / 1000)  # kg
                
                # Composição do óleo e fatores de metabolização
                pOleic = composicao_oleo_inv[0]
                pLinoleic = composicao_oleo_inv[1]
                pLinolenic = composicao_oleo_inv[3]
                mLinoleic = composicao_oleo_inv[5]
                mLinolenic = composicao_oleo_inv[6]
                
                # Efetividade total do óleo com base na composição
                efetividade = (
                    (pOleic / 100)
                    + (pLinoleic / 100) * (mLinoleic / 100)
                    + (pLinolenic / 100) * (mLinolenic / 100)
                )
                
                # Massa de óleo total necessária para fornecer o ácido oleico requerido
                massa_oleo_total_necessaria = massa_oleico_necessaria / efetividade  # kg
                
                # Sacarose equivalente
                sacarose_equivalente = glicose_necessaria * MM['sacarose'] / MM['glicose'] / 2  # kg
                
                # Mostrar resultados em tabela resumo
                st.subheader("Resultado estimado para atingir a meta:")
                resumo_df = pd.DataFrame({
                    'Descrição': [
                        'Glicose necessária (kg)',
                        'Sacarose total necessária (kg)',
                        'Ureia total necessária (kg)',
                        'Ácido oleico necessário (kg)',
                        'Efetividade do óleo (%)',
                        'Óleo total necessário (kg)',
                        'Sacarose equivalente (kg)'
                    ],
                    'Valor': [
                        f"{glicose_necessaria:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['massa_sacarose_total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['massa_ureia_total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{massa_oleico_necessaria:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{efetividade * 100:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{massa_oleo_total_necessaria:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{sacarose_equivalente:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ]
                })
                st.dataframe(resumo_df, use_container_width=True)
                
                # Calcular resultados completos
                params_inv['massa_oleo_total'] = massa_oleo_total_necessaria
                results = calcular_processo(params_inv, composicao_oleo_inv)
                
                st.header("Resultados Detalhados")
                if results['frasco']['volume_excedido']:
                    st.warning("Atenção: Volume total de insumos excede o volume do frasco!")
                if results['seed']['volume_excedido']:
                    st.warning("Atenção: Volume total de insumos excede o volume do seed!")
                if results['fermentador']['volume_excedido']:
                    st.warning("Atenção: Volume total de insumos excede o volume do fermentador!")
                if not results['fermentador']['aeracao_suficiente']:
                    st.warning(
                        f"⚠️ Espaço para aeração insuficiente no fermentador!\n"
                        f"- Percentual disponível: {results['fermentador']['percentual_aeracao']:.1f}%\n"
                        f"- Mínimo recomendado: 15.0%"
                    )

                st.subheader("Resumo Comparativo")

                # Inversão de eixos - etapas nas colunas, parâmetros nas linhas
                df = pd.DataFrame({
                    'Parâmetro': [
                        'Volume (L)',
                        'Sacarose Consumida (kg)',
                        'Ureia Consumida (kg)',
                        'Açúcares Fermentáveis (kg)',
                        'Biomassa Produzida (kg)',
                        'Óleo Total (kg)',
                        'Óleo Metabolizável (kg)',
                        'Óleo Consumido (kg)',
                        'Óleo Residual (kg)',
                        'Etanol (L)',
                        'HCl (L)',
                        'Volume Insumos (L)',
                        'Volume Água (L)',
                        'Espaço para Aeração (%)'
                    ],
                    'Frasco': [
                        f"{results['frasco']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['volume_insumos']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['volume_agua']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['frasco']['percentual_aeracao']:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00"
                    ],
                    'Seed': [
                        f"{results['seed']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['volume_insumos']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['volume_agua']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['seed']['percentual_aeracao']:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00",
                        "0,00"
                    ],
                    'Fermentador': [
                        f"{results['fermentador']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['volume_insumos']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['volume_agua']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['percentual_aeracao']:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['massa_oleo_total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['oleo_efetivo']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['oleo_consumido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['oleo_residual']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['ethanol']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['hcl']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

                    ]
                })

                # Configure o DataFrame para mostrar o parâmetro como índice para melhor visualização
                df = df.set_index('Parâmetro')
                st.dataframe(df, use_container_width=True, height=400)

                # st.info(f"Informações adicionais:\n"
                # f"- Água mínima necessária para reações: {results['agua_minima_reacao']:.2f} kg\n"
                # f"- Espaço disponível para aeração: {results['percentual_aeracao']:.1f}%\n"
                # f"- Espaço mínimo recomendado: 15.0%")

                # st.info(f"Informações adicionais:\n"
                # f"- Água gerada durante as reações: {results['agua_gerada']:,.2f} kg\n"
                # f"- Espaço para aeração no fermentador: {results['fermentador']['percentual_aeracao']:,.1f}%\n"
                # f"- Espaço mínimo recomendado: 15.0%\n"
                # f"- Percentual de meio no fermentador: {100 - results['fermentador']['percentual_aeracao']:,.1f}%")

                # Adiciona a tabela de água e sais necessários
                st.subheader("Água e Sais Minerais Necessários")
                insumos_df = pd.DataFrame({
                    'Parâmetro': ['Água (L)', 'Sais Minerais (kg)'],
                    'Frasco': [
                        f"{results['agua_necessaria']['frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['sais_necessarios']['frasco']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ],
                    'Seed': [
                        f"{results['agua_necessaria']['seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['sais_necessarios']['seed']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ],
                    'Fermentador': [
                        f"{results['agua_necessaria']['fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['sais_necessarios']['fermentador']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ],
                    'Total': [
                        f"{results['agua_necessaria']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['sais_necessarios']['total']:,.3f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ]
                })
                insumos_df = insumos_df.set_index('Parâmetro')
                st.dataframe(insumos_df, use_container_width=True)

if __name__ == "__main__":
    main()
