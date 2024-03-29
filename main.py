from discord_components import ComponentsBot

from command.admin_command import decay, adjust
from command.raider_command import update_user_id, check_pr, reset_spec

from infra.source import load_loot_from_json_to_memory, load_epgp_from_json_to_memory

from view.menu.loot_menu import boss_menu, loot_menu
from view.view import send_initial_message, update_admin_view, update_raider_view

from menu_callback.loot_callback import loot_announcement

from emojis import emojis

from infra.source import dump_epgp_from_memory_to_json

import asyncio
import cfg
import constant
import discord
import history
import json
import re
import util

import raider

bot = ComponentsBot('?')
history.start_logger()

discord_token = None
admin_user_id = None
with open('local_settings.json') as infile:
    data = json.load(infile)
    discord_token = data['discord_token']
    admin_user_id = int(data['admin_user_id'])

cfg.raider_dict = {}
cfg.loot_dict = {}
cfg.emojis_dict = {}

cfg.is_distributing = False


@bot.event
async def on_ready():
    load_loot_from_json_to_memory()
    load_epgp_from_json_to_memory()

    cfg.raider_channel = await bot.fetch_channel(constant.loot_channel)
    cfg.admin_channel = await bot.fetch_user(admin_user_id)

    raid_voice_channel = await bot.fetch_channel(constant.raid_channel)
    for user_id in raid_voice_channel.voice_states.keys():
        for name, raider in cfg.raider_dict.items():
            if user_id in raider.user_id:
                raider.in_raid = True

    async for message in cfg.raider_channel.history():
        await message.delete()

    async for message in cfg.admin_channel.history():
        if message.author.id != admin_user_id:
            await message.delete()

    for name, id in emojis.items():
        cfg.emojis_dict.update({name: bot.get_emoji(id)})

    await send_initial_message()

    print('CF Senior EPGP start')

    # lua_result = ''
    # for name, raider in cfg.raider_dict.items():
    #   lua_result += name + "= {"
    #   lua_result += "[\"ep\"] = " + str(raider.ep) + ","
    #   lua_result += "[\"gp\"] = " + str(raider.gp) + ","
    #   lua_result += "[\"spec\"] = " + str(raider.spec) + "},"

    # loot_result = ''

    # for name, loot in cfg.loot_dict.items():
    #   loot_result += "[\"" + name + "\"] = {"
    #   loot_result += "[\"gp\"] = " + str(loot.gp) + ","
    #   if(len(loot.bis) == 0):
    #     loot_result += "[\"bis\"] = {},},"
    #   else:
    #     loot_result += "[\"bis\"] = {"
    #     for single_bis in loot.bis:
    #       loot_result += str(single_bis) + ","
    #     loot_result += "}, },"

    # print(lua_result)


@bot.event
async def on_voice_state_update(member, before, after):
    if (len(cfg.raider_dict) == 0):
        return

    new_channel = after.channel
    before_channel = before.channel

    if (new_channel is not None and new_channel.id == constant.raid_channel):
        print('%s joined server %s' % (member.name, member.id))

        for raider in cfg.raider_dict.values():
            if member.id in raider.user_id:
                raider.in_raid = True
                await update_raider_view()
                break
    elif ((new_channel is None or new_channel.id != constant.raid_channel)
          and (before_channel is not None)
          and (before_channel.id == constant.raid_channel)):
        print('%s left server' % (member.name))

        for raider in cfg.raider_dict.values():
            if member.id in raider.user_id:
                raider.in_raid = False
                await update_raider_view()
                break


@bot.event
async def on_message(message):
    if (type(message.channel) is not discord.DMChannel):
        return

    if (message.author == bot.user):
        return

    if (util.is_match(constant.spec_reg, message.content)):
        await reset_spec(message)

    if (util.is_match(constant.pr_reg, message.content)):
        await check_pr(message)

    if (util.is_match(constant.decay_reg, message.content)):
        await decay(message)

    if (util.is_match(constant.adjust_reg, message.content)):
        await adjust(message)

    if (util.is_match(constant.update_reg, message.content)):
        await update_user_id(message)

    if (util.is_match(constant.write_reg, message.content)):
        dump_epgp_from_memory_to_json()
        await message.channel.send('写入成功', delete_after=constant.delte_after)


@bot.event
async def on_button_click(interaction):
    custom_id = interaction.custom_id

    if (custom_id == None):
        await interaction.respond(type=constant.edit_message_response_type)
        return
    elif (custom_id.startswith('loot')):
        user_id = interaction.user.id
        loot_name = custom_id.split(' ')[1]

        if (util.find_raider_name(user_id) == None):
            # TODO: Consider response with another response type other than edit message, also with real message
            await interaction.respond(type=constant.edit_message_response_type)
            return

        if (user_id in cfg.main_spec[loot_name]
                or user_id in cfg.off_spec[loot_name]
                or user_id in cfg.minor_improve[loot_name]
                or user_id in cfg.gbid[loot_name]):
            await interaction.respond(type=constant.edit_message_response_type)
            return

        if (custom_id.startswith(constant.loot_main_spec_id)):
            cfg.main_spec[loot_name].append(interaction.user.id)
        elif (custom_id.startswith(constant.loot_off_spec_id)):
            cfg.off_spec[loot_name].append(interaction.user.id)
        elif (custom_id.startswith(constant.loot_minor_improve_id)):
            cfg.minor_improve[loot_name].append(interaction.user.id)
        elif (custom_id.startswith(constant.loot_gbid_id)):
            cfg.gbid[loot_name].append(interaction.user.id)

        await interaction.respond(type=constant.edit_message_response_type)
    elif (custom_id.startswith('admin')):
        if (util.is_match(custom_id, constant.admin_cancel_id)):
            cfg.next_menu = boss_menu()
            await update_admin_view()

        if (util.is_match(custom_id, constant.admin_reward_20_id)):
            for raider in cfg.raider_dict.values():
                if (raider.in_raid == True):
                    util.set_ep(raider.name, raider.ep + 20)
            await update_raider_view()
            history.log_msg('All Raider 20EP')

        if (util.is_match(custom_id, constant.admin_reward_150_id)):
            for raider in cfg.raider_dict.values():
                if (raider.in_raid == True):
                    util.set_ep(raider.name, raider.ep + 150)
            await update_raider_view()
            history.log_msg('All Raider 150EP')

        if (util.is_match(custom_id, constant.admin_reward_200_id)):
            for raider in cfg.raider_dict.values():
                if (raider.in_raid == True):
                    util.set_ep(raider.name, raider.ep + 200)
            await update_raider_view()
            history.log_msg('All Raider 200EP')

        if (util.is_match(custom_id, constant.admin_reward_250_id)):
            for raider in cfg.raider_dict.values():
                if (raider.in_raid == True):
                    util.set_ep(raider.name, raider.ep + 250)
            await update_raider_view()
            history.log_msg('All Raider 250EP')

    await interaction.respond(type=constant.edit_message_response_type)


@bot.event
async def on_select_option(interaction):
    if (len(interaction.values) == 0):
        return

    if (interaction.custom_id == constant.boss_menu_id):
        cfg.next_menu = loot_menu(interaction.values[0])
        await update_admin_view()
        await interaction.respond(type=constant.edit_message_response_type)
    elif (interaction.custom_id == constant.loot_menu_id):
        cfg.next_menu = boss_menu()
        asyncio.create_task(loot_announcement(interaction.values))
        await update_admin_view()
        await interaction.respond(type=constant.edit_message_response_type)
    elif (interaction.custom_id.startswith('distribute')):
        # TODO: consider extract this part to common util and prevent the interaction happen twice
        # the custom id should in format of 'distribute -loot %s -percentage %s'
        # Support multi raiders distribute
        raider_name = interaction.values[0]
        loot_name = re.findall("-loot ([^ ]+)", interaction.custom_id,
                               re.IGNORECASE)[0]
        percentage = int(
            re.findall("-percentage ([0-9]+)", interaction.custom_id,
                       re.IGNORECASE)[0]) / 100
        util.set_gp(
            raider_name, cfg.raider_dict[raider_name].gp +
            int(cfg.loot_dict[loot_name].gp * percentage))

        await interaction.respond(type=constant.edit_message_response_type)
        await interaction.message.delete()

        history.log_adjustment([raider_name],
                               loot=cfg.loot_dict[loot_name],
                               gp=int(cfg.loot_dict[loot_name].gp *
                                      percentage),
                               percentage=percentage)

        await update_raider_view()


#bot.run(discord_token)
result = '{[Hunterbear][11594][15484]}{[Wspriest][10944][12855]}{[Ishotokill][8393][14835]}{[Ronaldoluis][11244][6218]}{[Udyin][7687][8507]}{[Spoondz][7728][12707]}{[Pandafree][10670][11515]}{[Bansheegd][12087][13130]}{[Lowkeyrunner][12177][35739]}{[Nons][12165][16562]}{[Dagugu][5195][7027]}{[Bloodmagus][10898][601]}{[Norva][8998][4228]}{[Airbkb][2452][1655]}{[Doubleverify][10323][14882]}{[Mihoyo][10042][5678]}{[Deleva][8023][8555]}{[Spoond][7264][5100]}{[Eaturtofu][1995][3857]}{[Burninglove][11766][4551]}{[Valdmire][5550][850]}{[Threesomer][3496][2434]}{[Bubusasa][6570][11292]}{[Akitainu][12167][9197]}{[Yuuluve][6570][7308]}{[Milkbig][8443][5727]}{[Thewindrises][12163][11643]}{[Everchild][11983][15827]}{[Springg][10492][15719]}{[Mortalzelda][10629][7890]}{[Merlinni][6570][850]}'
all_chars = re.findall("(\{\[[A-Z]+\]\[[0-9]+\]\[[0-9]+\]\})", result, re.IGNORECASE)

for char in all_chars:
  name_match = re.findall("\[[A-Z]+\]", char, re.IGNORECASE)[0]
  name = name_match[1:len(name_match) - 1]

  scores_match = re.findall("(\[[0-9]+\])", char, re.IGNORECASE)
  ep = int(scores_match[0][1:len(scores_match[0]) - 1])
  gp = int(scores_match[1][1:len(scores_match[1]) - 1])

  cfg.raider_dict[name] = raider.Raider(name, ep, gp, 1, 1)

dump_epgp_from_memory_to_json()