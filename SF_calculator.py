import streamlit as st
import pandas as pd
import numpy as np

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
    return volume_total, volume_total > volume_maximo

def calcular_agua_necessaria(params, results):
    # Calcula volume ocupado pelos sólidos em cada etapa
    densidade_sacarose = 1.56  # g/cm³
    densidade_ureia = 1.32  # g/cm³
    densidade_oleo = 0.92  # g/cm³
    
    # Frasco
    vol_sacarose_frasco = results['frasco']['sacarose_consumida'] * 1000 / densidade_sacarose
    vol_ureia_frasco = results['frasco']['ureia_consumida'] * 1000 / densidade_ureia
    vol_solidos_frasco = vol_sacarose_frasco + vol_ureia_frasco
    agua_frasco = max(0, params['volume_frasco'] * 1000 - vol_solidos_frasco)  # em mL
    
    # Seed
    vol_sacarose_seed = results['seed']['sacarose_consumida'] * 1000 / densidade_sacarose
    vol_ureia_seed = results['seed']['ureia_consumida'] * 1000 / densidade_ureia
    vol_solidos_seed = vol_sacarose_seed + vol_ureia_seed
    # Subtrai o volume do inóculo vindo do frasco
    agua_seed = max(0, params['volume_seed'] * 1000 - vol_solidos_seed - results['seed']['volume_inoculo'] * 1000)
    
    # Fermentador
    vol_sacarose_ferm = results['fermentador']['sacarose_consumida'] * 1000 / densidade_sacarose
    vol_ureia_ferm = results['fermentador']['ureia_consumida'] * 1000 / densidade_ureia
    vol_oleo_ferm = params['massa_oleo_total'] * 1000 / densidade_oleo
    vol_solidos_ferm = vol_sacarose_ferm + vol_ureia_ferm + vol_oleo_ferm
    # Subtrai o volume do inóculo vindo do seed
    agua_ferm = max(0, params['volume_fermentador'] * 1000 - vol_solidos_ferm - results['fermentador']['volume_inoculo'] * 1000)
    
    # Converte de mL para L
    return {
        'frasco': agua_frasco / 1000,
        'seed': agua_seed / 1000,
        'fermentador': agua_ferm / 1000,
        'total': (agua_frasco + agua_seed + agua_ferm) / 1000
    }


def calcular_processo(params, composicao_oleo):
    total_volume = params['volume_frasco'] + params['volume_seed'] + params['volume_fermentador']
    prop_frasco = params['volume_frasco'] / total_volume
    prop_seed = params['volume_seed'] / total_volume
    prop_ferm = params['volume_fermentador'] / total_volume

    massa_sacarose_frasco = params['massa_sacarose_total'] * prop_frasco
    massa_sacarose_seed = params['massa_sacarose_total'] * prop_seed
    massa_sacarose_ferm = params['massa_sacarose_total'] * prop_ferm
    massa_ureia_frasco = params['massa_ureia_total'] * prop_frasco
    massa_ureia_seed = params['massa_ureia_total'] * prop_seed
    massa_ureia_ferm = params['massa_ureia_total'] * prop_ferm
    massa_oleo_ferm = params['massa_oleo_total']

    vol_frasco_calc, excedido_frasco = calcular_volume_etapa(massa_sacarose_frasco, massa_ureia_frasco, 0, params['volume_frasco'])
    vol_seed_calc, excedido_seed = calcular_volume_etapa(massa_sacarose_seed, massa_ureia_seed, 0, params['volume_seed'])
    vol_ferm_calc, excedido_ferm = calcular_volume_etapa(massa_sacarose_ferm, massa_ureia_ferm, massa_oleo_ferm, params['volume_fermentador'])

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
    soforo_result = calc_soforolipideo(ferm_glicose_soforo, massa_oleo_ferm, params['rend_soforolipideo'], composicao_oleo)

    results = {
        'frasco': {
            'volume': params['volume_frasco'],
            'sacarose_consumida': massa_sacarose_frasco,
            'ureia_consumida': massa_ureia_frasco,
            'acucares_fermentaveis': frasco_acucares,
            'biomassa_produzida': frasco_biomassa,
            'soforolipideo_produzido': 0,
            'conc_biomassa': frasco_biomassa * 1000 / params['volume_frasco'],
            'volume_excedido': excedido_frasco
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
            'volume_excedido': excedido_seed
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
            'volume_excedido': excedido_ferm
        }
    }
    # Calcula a água necessária
    agua = calcular_agua_necessaria(params, results)
    results['agua_necessaria'] = agua
    
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
    # Calcula glicose necessária para atingir a meta
    glicose_necessaria = massa_soforolipideo_alvo / params_inv['rend_soforolipideo']
    
    # Mols de glicose
    mols_glicose = glicose_necessaria / (MM['glicose'] / 1000)
    
    # Mols de ácido oleico necessários (estequiometria 4:1)
    mols_oleico_necessario = mols_glicose / 4
    
    # Massa de ácido oleico necessária
    massa_oleico_necessaria = mols_oleico_necessario * (MM['acidoOleico'] / 1000)
    
    # Calcula efetividade do óleo baseado na composição
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
    
    # Massa de óleo total necessária
    massa_oleo_total_necessaria = massa_oleico_necessaria / efetividade
    
    # Calcula volume do fermentador baseado na concentração típica de soforolipídeos
    conc_soforolipideo_tipica = params_inv['conc_soforolipideo_alvo'] if 'conc_soforolipideo_alvo' in params_inv else 20  # g/L
    volume_fermentador = massa_soforolipideo_alvo * 1000 / conc_soforolipideo_tipica
    
    # Dimensiona o seed e o frasco baseado nas proporções de inóculo
    volume_seed = volume_fermentador * params_inv['prop_inoculo_seed'] * 10  # Fator de segurança 10x
    volume_frasco = volume_seed * params_inv['prop_inoculo_frasco'] * 10  # Fator de segurança 10x
    
    # Atualiza os parâmetros
    params_inv['volume_fermentador'] = volume_fermentador
    params_inv['volume_seed'] = volume_seed
    params_inv['volume_frasco'] = volume_frasco
    params_inv['massa_oleo_total'] = massa_oleo_total_necessaria
    
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
        unidade_sacarose = st.selectbox("Unidade Sacarose", ["Concentração (g/L)", "Quantidade Total (kg)"], key='us1')
        unidade_ureia = st.selectbox("Unidade Ureia", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uu1')
        unidade_oleo = st.selectbox("Unidade Óleo", ["Concentração (g/L)", "Quantidade Total (kg)"], key='uo1')

        # Organizar em 3 colunas com 5 linhas cada
        col1, col2, col3 = st.columns(3)
        params = {}

        # Coluna 1
        with col1:
            params['volume_frasco'] = st.number_input('Volume Frasco (L)', value=1.0, format="%.2f", key='vf1')
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
            params['volume_seed'] = st.number_input('Volume Seed (L)', value=500.0, format="%.2f", key='vs1')
            params['rend_biomassa'] = st.number_input('Rend. Biomassa (g/g)', value=0.678, format="%.3f", key='rb1')
            params['rend_soforolipideo'] = st.number_input('Rend. Soforolipídeo (g/g)', value=0.722, format="%.3f", key='rs1')
            params['ferment_time'] = st.number_input('Tempo Fermentação (h)', value=168.0, format="%.2f", key='ft1')
            params['prop_inoculo_frasco'] = st.number_input('Prop. Inóculo Frasco→Seed', value=0.01, format="%.2f", key='pif1')

        # Coluna 3
        with col3:
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

        st.info(f"🔍 Estimativa: Para atender à glicose disponível, são necessários aproximadamente {massa_oleo_ideal:,.2f} kg de óleo.")

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

        if st.button("Calcular", key='calc1'):
            percentual_efetividade_estimado = composicao_oleo[0]/100 + (composicao_oleo[1]/100)*(composicao_oleo[5]/100) + (composicao_oleo[3]/100)*(composicao_oleo[6]/100)
            oleo_total_estimado = massa_oleo_ideal / percentual_efetividade_estimado
            st.info(
                f"🔍 Estimativa baseada na composição do óleo:\n"
                f"- Ácidos graxos metabolizáveis necessários: {massa_oleo_ideal:,.2f} kg\n"
                f"- Eficiência metabólica do óleo: {percentual_efetividade_estimado*100:,.1f}%\n"
                f"- Óleo total recomendado: {oleo_total_estimado:,.2f} kg"
            )
            results = calcular_processo(params, composicao_oleo)
            st.header("Resultados")
            if results['frasco']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do frasco!")
            if results['seed']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do seed!")
            if results['fermentador']['volume_excedido']:
                st.warning("Atenção: Volume total de insumos excede o volume do fermentador!")            
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
                    "0,00"
                ],
                'Fermentador': [
                    f"{results['fermentador']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                    f"{results['fermentador']['soforolipideo_produzido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
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

            # Adiciona a tabela de água necessária
            st.subheader("Água Necessária")
            agua_df = pd.DataFrame({
                'Parâmetro': ['Água (L)'],
                'Frasco': [f"{results['agua_necessaria']['frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                'Seed': [f"{results['agua_necessaria']['seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                'Fermentador': [f"{results['agua_necessaria']['fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                'Total': [f"{results['agua_necessaria']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')]
            })
            agua_df = agua_df.set_index('Parâmetro')
            st.dataframe(agua_df, use_container_width=True)

            # st.subheader("Água Necessária")
            # agua_df = pd.DataFrame({
            #     'Etapa': ['Frasco', 'Seed', 'Fermentador', 'Total'],
            #     'Água (L)': [
            #         f"{results['agua_necessaria']['frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            #         f"{results['agua_necessaria']['seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            #         f"{results['agua_necessaria']['fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            #         f"{results['agua_necessaria']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            #     ]
            # })

            # st.dataframe(agua_df, use_container_width=True)

    with tab2:
        st.header("Cálculo Inverso: Quantidade de insumos necessários para a meta de produção")

        # Organizar em 3 colunas com 4 linhas cada
        col1, col2, col3 = st.columns(3)
        params_inv = {}

        # Coluna 1
        with col1:
            massa_soforolipideo_alvo = st.number_input("Meta Soforolipídeo (kg)", value=100.0, format="%.2f", key='sd2')
            conc_soforolipideo_alvo = st.number_input("Conc. Soforolipídeo (g/L)", value=20.0, format="%.2f", key='csd2')
            params_inv['massa_sacarose_total'] = st.number_input('Massa Sacarose (kg)', value=500.0, format="%.2f", key='ms2')
            params_inv['ethanol_per_kg'] = st.number_input('Etanol por kg Soforolip. (L)', value=2.0, format="%.2f", key='epk2')
            params_inv['hcl_per_l'] = st.number_input('HCl por L de Óleo (L/L)', value=2.0, format="%.2f", key='hpl2')
            params_inv['conc_soforolipideo_alvo'] = conc_soforolipideo_alvo

        # Coluna 2
        with col2:
            params_inv['massa_ureia_total'] = st.number_input('Massa Ureia (kg)', value=25.0, format="%.2f", key='mu2')
            params_inv['prop_glicose_biomassa'] = st.number_input('Prop. Glicose p/ Biomassa (%)', value=20.0, format="%.2f", key='pgb2') / 100
            params_inv['rend_biomassa'] = st.number_input('Rend. Biomassa (g/g)', value=0.678, format="%.3f", key='rb2')
            params_inv['rend_soforolipideo'] = st.number_input('Rend. Soforolipídeo (g/g)', value=0.722, format="%.3f", key='rs2')

        # Coluna 3
        with col3:
            params_inv['ferment_time'] = st.number_input('Tempo Fermentação (h)', value=168.0, format="%.2f", key='ft2')
            params_inv['seed_time'] = st.number_input('Tempo Incubação Seed (h)', value=24.0, format="%.2f", key='st2')
            params_inv['prop_inoculo_frasco'] = st.number_input('Prop. Inóculo Frasco→Seed', value=0.01, format="%.2f", key='pif2')
            params_inv['prop_inoculo_seed'] = st.number_input('Prop. Inóculo Seed→Ferm.', value=0.1, format="%.2f", key='pis2')


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
                
                # Exibe os tamanhos calculados dos biorreatores
                st.success("🧪 Biorreatores dimensionados para atingir a meta:")
                biorreatores_df = pd.DataFrame({
                    'Biorreator': ['Frasco', 'Seed', 'Fermentador'],
                    'Volume Calculado (L)': [
                        f"{params_inv['volume_frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['volume_seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{params_inv['volume_fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    ]
                })
                st.dataframe(biorreatores_df, use_container_width=True)
                
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
                st.success("🧪 Resultado estimado para atingir a meta:")
                resumo_df = pd.DataFrame({
                    'Descrição': [
                        'Glicose necessária (kg)',
                        'Ácido oleico necessário (kg)',
                        'Efetividade do óleo (%)',
                        'Óleo total necessário (kg)',
                        'Sacarose equivalente (kg)'
                    ],
                    'Valor': [
                        f"{glicose_necessaria:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
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
                        "0,00"
                    ],
                    'Fermentador': [
                        f"{results['fermentador']['volume']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['sacarose_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['ureia_consumida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['acucares_fermentaveis']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['biomassa_produzida']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        f"{results['fermentador']['soforolipideo_produzido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
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

                # Adiciona a tabela de água necessária
                st.subheader("Água Necessária")
                agua_df = pd.DataFrame({
                    'Parâmetro': ['Água (L)'],
                    'Frasco': [f"{results['agua_necessaria']['frasco']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                    'Seed': [f"{results['agua_necessaria']['seed']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                    'Fermentador': [f"{results['agua_necessaria']['fermentador']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                    'Total': [f"{results['agua_necessaria']['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')]
                })
                agua_df = agua_df.set_index('Parâmetro')
                st.dataframe(agua_df, use_container_width=True)
if __name__ == "__main__":
    main()
